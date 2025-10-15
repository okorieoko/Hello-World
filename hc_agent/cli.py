import typer
from typing import List, Optional
from .cms import CmsClient, fetch_inpatient_drg_year
from .match import map_terms_to_drgs
from .aggregate import aggregate_by_year
from .viz import render_plot
from .local import load_local_csv

app = typer.Typer(help="Compare healthcare costs for hospital admissions over the last 10 years.")

@app.command()
def compare(
    terms: List[str] = typer.Argument(..., help="Admission terms (e.g., pneumonia, heart failure)"),
    state: Optional[str] = typer.Option(None, help="US state postal code to filter (e.g., CA)"),
    min_score: int = typer.Option(85, help="Minimum fuzzy match score for DRG mapping (0-100)"),
    save_csv: Optional[str] = typer.Option(None, help="Path to save aggregated CSV"),
    show_chart: bool = typer.Option(False, help="Display a comparison chart"),
    csv_path: Optional[str] = typer.Option(None, help="Use local CSV instead of CMS API"),
):
    import pandas as pd

    if csv_path:
        # Local CSV mode
        df_all = load_local_csv(csv_path, state=state)
        years = sorted(df_all["year"].dropna().unique().tolist())[-10:]
        typer.echo(f"Using years: {years}")
        drg_definitions = (
            df_all["drg_definition"].dropna().astype(str).unique().tolist()
        )
        mapping = map_terms_to_drgs(terms, drg_definitions, min_score=min_score)
        per_term_results = {}
        for term, matched in mapping.items():
            matched_drg_defs = [m.definition for m in matched]
            yearly_frames = []
            for year in years:
                df_year = df_all[df_all["year"] == year]
                df_term = df_year[df_year["drg_definition"].isin(matched_drg_defs)].copy()
                if df_term.empty:
                    continue
                df_term["year"] = year
                yearly_frames.append(df_term)
            if yearly_frames:
                term_df = aggregate_by_year(yearly_frames)
                term_df["term"] = term
                per_term_results[term] = term_df
    else:
        client = CmsClient()
        # Discover last 10 years available for inpatient DRG dataset
        years = client.available_years(limit=10)
        if not years:
            typer.echo("No years available from CMS dataset.")
            raise typer.Exit(code=1)

        typer.echo(f"Using years: {years}")

        # Fetch DRGs catalog for matching (union across years)
        all_year_frames = []
        for year in years:
            df = fetch_inpatient_drg_year(client, year, state=state)
            if df is not None and not df.empty:
                all_year_frames.append(df[["drg_definition"]].drop_duplicates())
        if not all_year_frames:
            typer.echo("No data fetched from CMS.")
            raise typer.Exit(code=1)

        drg_catalog = pd.concat(all_year_frames).drop_duplicates().reset_index(drop=True)
        drg_definitions = drg_catalog["drg_definition"].dropna().astype(str).unique().tolist()

        mapping = map_terms_to_drgs(terms, drg_definitions, min_score=min_score)

        # Aggregate across years per term
        per_term_results = {}
        for term, matched in mapping.items():
            matched_drg_defs = [m.definition for m in matched]
            yearly_frames = []
            for year in years:
                df = fetch_inpatient_drg_year(client, year, state=state)
                if df is None or df.empty:
                    continue
                df_term = df[df["drg_definition"].isin(matched_drg_defs)].copy()
                if df_term.empty:
                    continue
                df_term["year"] = year
                yearly_frames.append(df_term)
            if yearly_frames:
                term_df = aggregate_by_year(yearly_frames)
                term_df["term"] = term
                per_term_results[term] = term_df

    if not per_term_results:
        typer.echo("No matching DRGs found for provided terms.")
        raise typer.Exit(code=1)

    result = pd.concat(per_term_results.values(), ignore_index=True)

    typer.echo("\nAggregated results (weighted by discharges):")
    typer.echo(result.to_string(index=False))

    if save_csv:
        result.to_csv(save_csv, index=False)
        typer.echo(f"Saved CSV to {save_csv}")

    if show_chart:
        render_plot(result)

if __name__ == "__main__":
    app()
