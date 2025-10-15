# Healthcare Admission Cost Comparison Agent

Compare healthcare costs for various hospital admissions (DRG) over the past 10 years using CMS data. Falls back to a local CSV if the CMS Socrata API is unavailable.

## Quickstart

1) Install (editable):

```bash
python3 -m pip install -e .
```

2) Run with local CSV fallback (sample provided):

```bash
python3 -m hc_agent.cli compare pneumonia "heart failure" \
  --state CA \
  --min-score 70 \
  --csv-path ./sample_drg.csv \
  --save-csv ./out.csv
```

3) To use CMS API (if accessible):

```bash
python3 -m hc_agent.cli compare pneumonia "heart failure" --state CA --min-score 80
```

Optional: set a Socrata app token for higher limits:

```bash
export CMS_SOCRATA_APP_TOKEN=your_token_here
```

## Notes
- Fuzzy matching maps free-text terms to DRG definitions.
- Aggregation computes discharge-weighted averages per year for covered charges, total payments, and Medicare payments.
- Use `--show-chart` to visualize trends (requires a GUI-enabled environment).
