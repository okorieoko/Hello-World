import pandas as pd
from typing import List

# Weighted averages by total discharges

def aggregate_by_year(frames: List[pd.DataFrame]) -> pd.DataFrame:
    df = pd.concat(frames, ignore_index=True)
    # group by year
    if "year" not in df.columns:
        raise ValueError("Input frames must include 'year' column")

    def weighted_avg(group: pd.DataFrame, value_col: str) -> float:
        weights = group["total_discharges"].fillna(0)
        values = group[value_col].fillna(0)
        denom = weights.sum()
        if denom == 0:
            return float("nan")
        return (values * weights).sum() / denom

    out = (
        df.groupby(["year"]).apply(
            lambda g: pd.Series({
                "weighted_avg_covered_charges": weighted_avg(g, "average_covered_charges"),
                "weighted_avg_total_payments": weighted_avg(g, "average_total_payments"),
                "weighted_avg_medicare_payments": weighted_avg(g, "average_medicare_payments"),
                "total_discharges": g["total_discharges"].sum(),
            })
        ).reset_index()
    )
    return out.sort_values("year")
