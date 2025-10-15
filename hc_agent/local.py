import pandas as pd
from typing import Optional

REQUIRED_COLUMNS = [
    "year",
    "drg_definition",
    "provider_state",
    "total_discharges",
    "average_covered_charges",
    "average_total_payments",
    "average_medicare_payments",
]


def load_local_csv(path: str, state: Optional[str] = None) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Normalize columns
    rename_map = {
        "fiscal_year": "year",
        "state": "provider_state",
    }
    for old, new in rename_map.items():
        if old in df.columns and new not in df.columns:
            df = df.rename(columns={old: new})
    # Ensure required columns exist
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")
    # Ensure numeric types
    for col in [
        "total_discharges",
        "average_covered_charges",
        "average_total_payments",
        "average_medicare_payments",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if state:
        df = df[df["provider_state"].str.upper() == state.upper()]
    return df
