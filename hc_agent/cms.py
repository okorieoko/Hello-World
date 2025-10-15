import os
import requests
import pandas as pd
from typing import List, Optional, Dict, Tuple

SOC_APP_TOKEN_ENV = "CMS_SOCRATA_APP_TOKEN"

"""
CMS inpatient DRG costs via Socrata (data.cms.gov)

We dynamically discover a dataset that contains the required columns using the
Socrata Catalog API, since dataset IDs may change over time.
"""

# Preferred column names and synonyms to tolerate schema drift
PREFERRED_COLUMNS: Dict[str, Tuple[str, ...]] = {
    "year": ("fiscal_year", "year", "reporting_year", "report_year"),
    "drg_definition": ("drg_definition",),
    "state": ("provider_state", "state"),
    "total_discharges": ("total_discharges", "discharges"),
    "average_covered_charges": ("average_covered_charges", "avg_covered_charges"),
    "average_total_payments": ("average_total_payments", "avg_total_payments"),
    "average_medicare_payments": ("average_medicare_payments", "avg_medicare_payments"),
}

class CmsClient:
    def __init__(self, app_token: Optional[str] = None) -> None:
        self.base = "https://data.cms.gov/resource"
        self.catalog = "https://api.us.socrata.com/api/catalog/v1"
        self.app_token = app_token or os.getenv(SOC_APP_TOKEN_ENV)
        self.dataset_id: Optional[str] = None
        self.columns_map: Optional[Dict[str, str]] = None

    def _headers(self):
        headers = {"Accept": "application/json"}
        if self.app_token:
            headers["X-App-Token"] = self.app_token
        return headers

    def _discover_dataset(self) -> None:
        # Use Socrata catalog to find a dataset with required columns
        params = {
            "domains": "data.cms.gov",
            "search_context": "data.cms.gov",
            "only": "datasets",
            "q": "inpatient drg provider summary",
            "limit": 50,
        }
        try:
            resp = requests.get(self.catalog, headers=self._headers(), params=params, timeout=30)
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception:
            results = []

        best_candidate = None
        best_columns: Dict[str, str] = {}

        def find_column(resource_cols: List[Dict[str, str]], candidates: Tuple[str, ...]) -> Optional[str]:
            names = {c.lower() for c in candidates}
            for col in resource_cols:
                name = (col.get("fieldName") or col.get("name") or "").lower()
                if name in names:
                    return col.get("fieldName") or col.get("name")
            # Try relaxed contains matching
            for col in resource_cols:
                name = (col.get("fieldName") or col.get("name") or "").lower()
                if any(token in name for token in names):
                    return col.get("fieldName") or col.get("name")
            return None

        for r in results:
            res = r.get("resource", {})
            if not res:
                continue
            cols = res.get("columns", [])
            # Build mapping
            mapping: Dict[str, str] = {}
            ok = True
            for logical, candidates in PREFERRED_COLUMNS.items():
                found = find_column(cols, candidates)
                if logical in ("state",):
                    # state is optional; we can fallback to no filter
                    if found:
                        mapping[logical] = found
                else:
                    if not found:
                        ok = False
                        break
                    mapping[logical] = found
            if not ok:
                continue
            # Prefer datasets that include "fiscal_year"
            year_field = mapping.get("year", "")
            score = 1 if year_field.lower() == "fiscal_year" else 0
            # Keep the first best match
            if best_candidate is None or score > best_candidate[0]:
                best_candidate = (score, res.get("id"))
                best_columns = mapping

        if best_candidate is None:
            # As a last resort, attempt a known ID used historically (may fail)
            self.dataset_id = "97k6-zzx3"
            self.columns_map = {
                "year": "fiscal_year",
                "drg_definition": "drg_definition",
                "state": "provider_state",
                "total_discharges": "total_discharges",
                "average_covered_charges": "average_covered_charges",
                "average_total_payments": "average_total_payments",
                "average_medicare_payments": "average_medicare_payments",
            }
        else:
            self.dataset_id = best_candidate[1]
            self.columns_map = best_columns

    def ensure_dataset(self) -> None:
        if self.dataset_id and self.columns_map:
            return
        self._discover_dataset()

    def available_years(self, limit: int = 10) -> List[int]:
        # Try querying distinct year from dataset; fallback to last N calendar years
        self.ensure_dataset()
        dataset = self.dataset_id
        year_col = self.columns_map.get("year", "fiscal_year") if self.columns_map else "fiscal_year"
        try:
            url = f"{self.base}/{dataset}.json"
            params = {
                "$select": f"distinct {year_col}",
                "$order": f"{year_col} DESC",
                "$limit": 1000,
            }
            resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            years = []
            for row in data:
                val = row.get(year_col)
                if val is None or val == "":
                    continue
                try:
                    years.append(int(val))
                except Exception:
                    # Sometimes fiscal year can be like "FY2019"; strip non-digits
                    import re as _re
                    m = _re.search(r"(\d{4})", str(val))
                    if m:
                        years.append(int(m.group(1)))
            years = sorted(set(years), reverse=True)[:limit]
            if years:
                return years
        except Exception:
            pass
        # Fallback: last N years
        import datetime as _dt
        current_year = _dt.datetime.now().year
        fallback = list(range(current_year, current_year - limit, -1))
        return fallback


def fetch_inpatient_drg_year(
    client: CmsClient,
    year: int,
    state: Optional[str] = None,
    limit: int = 50000,
) -> Optional[pd.DataFrame]:
    client.ensure_dataset()
    dataset = client.dataset_id
    cols = client.columns_map or {}

    url = f"{client.base}/{dataset}.json"
    year_col = cols.get("year", "fiscal_year")
    state_col = cols.get("state")
    where_clauses = [f"{year_col} = {year}"]
    if state and state_col:
        where_clauses.append(f"upper({state_col}) = '{state.upper()}'")

    select_cols = [
        cols.get("drg_definition", "drg_definition"),
        cols.get("total_discharges", "total_discharges"),
        cols.get("average_covered_charges", "average_covered_charges"),
        cols.get("average_total_payments", "average_total_payments"),
        cols.get("average_medicare_payments", "average_medicare_payments"),
    ]
    if state_col:
        select_cols.append(state_col)

    params = {
        "$select": ",".join(select_cols),
        "$where": " AND ".join(where_clauses),
        "$limit": limit,
    }

    try:
        resp = requests.get(url, headers=client._headers(), params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        df = pd.DataFrame(data)
        # Normalize column names to our logical names for downstream code
        rename_map = {}
        for logical, actual in cols.items():
            if logical in ("year",):
                continue
            if actual in df.columns:
                rename_map[actual] = logical if logical != "state" else "provider_state"
        if rename_map:
            df = df.rename(columns=rename_map)

        # Ensure numeric types
        for col in ["total_discharges", "average_covered_charges", "average_total_payments", "average_medicare_payments"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception:
        return None
