import pandas as pd
import matplotlib.pyplot as plt

def render_plot(result: pd.DataFrame) -> None:
    # Expect columns: year, weighted_avg_covered_charges, weighted_avg_total_payments, weighted_avg_medicare_payments, term
    if result.empty:
        return
    terms = result["term"].unique().tolist()
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharex=True)
    metrics = [
        ("weighted_avg_covered_charges", "Avg Covered Charges"),
        ("weighted_avg_total_payments", "Avg Total Payments"),
        ("weighted_avg_medicare_payments", "Avg Medicare Payments"),
    ]
    for idx, (col, title) in enumerate(metrics):
        ax = axes[idx]
        for term in terms:
            sub = result[result["term"] == term]
            ax.plot(sub["year"], sub[col], marker="o", label=term)
        ax.set_title(title)
        ax.set_xlabel("Year")
        ax.set_ylabel("USD")
        ax.grid(True, alpha=0.3)
        if idx == 0:
            ax.legend()
    plt.tight_layout()
    plt.show()
