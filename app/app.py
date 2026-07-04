"""Streamlit dashboard for Bangladesh Police crime statistics.

Reads the consolidated CSVs produced by scraper/pipeline.py and
scraper/scrape_year_table.py (data/bd_crime_monthly_master.csv and
data/bd_crime_annual_2010_2019.csv) and presents them as an interactive
dashboard: national/unit trends, crime-type breakdowns, and a dedicated
view for "recovery" cases (the r_* columns - cases where police recovered
arms, explosives, narcotics, or smuggled goods, as opposed to cases filed).
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_DIR = Path(__file__).parent.parent / "data"

CRIME_COLUMNS = {
    "dacoity": "Dacoity",
    "robbery": "Robbery",
    "murder": "Murder",
    "speedy_trial": "Speedy Trial Tribunal Cases",
    "riot": "Riot",
    "woman_child_repression": "Women & Child Repression",
    "kidnapping": "Kidnapping",
    "police_assault": "Police Assault",
    "burglary": "Burglary",
    "theft": "Theft",
    "other_cases": "Other Cases",
}

RECOVERY_COLUMNS = {
    "r_arms_act": "Arms Act",
    "r_explosive_act": "Explosive Act",
    "r_narcotics": "Narcotics Act",
    "r_smuggling": "Smuggling",
}

UNIT_ORDER = [
    "DMP", "CMP", "KMP", "RMP", "BMP", "SMP", "RPMP", "GMP", "ATU",
    "Dhaka Range", "Mymensingh Range", "Chittagong Range", "Sylhet Range",
    "Khulna Range", "Barishal Range", "Barisal Range", "Rajshahi Range",
    "Rangpur Range", "Railway Range",
]

MONTH_ORDER = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@st.cache_data
def load_monthly(path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[~df["is_annual_total"]]  # exclude the Jan-Dec total page - a duplicate of the year, not a 13th month
    df["month"] = pd.Categorical(df["month"], categories=MONTH_ORDER, ordered=True)
    df["period"] = pd.to_datetime(
        df["year"].astype(int).astype(str) + "-" + df["month"].astype(str), format="%Y-%B", errors="coerce"
    )
    return df


@st.cache_data
def load_annual() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "bd_crime_annual_2010_2019.csv")


def sorted_units(units: pd.Series) -> list[str]:
    present = list(units.dropna().unique())
    ordered = [u for u in UNIT_ORDER if u in present]
    ordered += sorted(u for u in present if u not in UNIT_ORDER and u != "Total")
    if "Total" in present:
        ordered.append("Total")
    return ordered


def render_kpis(df: pd.DataFrame, total_row: pd.DataFrame):
    total_cases = total_row["total_cases"].sum()
    total_recovery = total_row["total_recovery_cases"].sum()
    top_crime_col = df[list(CRIME_COLUMNS)].sum().idxmax() if not df.empty else None
    top_unit = (
        df[df["unit_name"] != "Total"].groupby("unit_name")["total_cases"].sum().idxmax()
        if not df[df["unit_name"] != "Total"].empty
        else "N/A"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Cases", f"{total_cases:,.0f}")
    c2.metric("Total Recovery Cases", f"{total_recovery:,.0f}")
    c3.metric("Most Common Crime", CRIME_COLUMNS.get(top_crime_col, "N/A"))
    c4.metric("Highest-Crime Unit", top_unit)


def render_breakdown_charts(df: pd.DataFrame):
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Crime Type Breakdown")
        crime_totals = df[list(CRIME_COLUMNS)].sum().rename(index=CRIME_COLUMNS)
        crime_totals = crime_totals.sort_values(ascending=True)
        fig = px.bar(
            crime_totals, orientation="h",
            labels={"value": "Cases", "index": ""},
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Recovery Cases Breakdown")
        st.caption(
            "Columns prefixed `r_` are **recovery cases** - instances where police "
            "recovered arms, explosives, narcotics, or smuggled goods - not filed "
            "criminal cases."
        )
        recovery_totals = df[list(RECOVERY_COLUMNS)].sum().rename(index=RECOVERY_COLUMNS)
        fig = px.pie(
            values=recovery_totals.values, names=recovery_totals.index, hole=0.4,
        )
        st.plotly_chart(fig, use_container_width=True)


def render_unit_comparison(df: pd.DataFrame):
    st.subheader("Cases by Unit")
    unit_totals = (
        df[df["unit_name"] != "Total"]
        .groupby("unit_name")["total_cases"].sum()
        .reindex(sorted_units(df["unit_name"]))
        .dropna()
    )
    fig = px.bar(unit_totals, labels={"value": "Total Cases", "unit_name": "Unit"})
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Total Cases")
    st.plotly_chart(fig, use_container_width=True)


def render_data_table(df: pd.DataFrame, key: str):
    st.subheader("Raw Data")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered data as CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"{key}.csv",
        mime="text/csv",
    )


def monthly_tab(master_path, key_prefix, source_note):
    df = load_monthly(master_path)

    st.sidebar.header(f"{key_prefix.title()} Filters")
    years = sorted(df["year"].dropna().unique())
    year_range = st.sidebar.select_slider(
        "Year range", options=years, value=(years[0], years[-1]), key=f"{key_prefix}_years"
    )
    unit_options = sorted_units(df["unit_name"])
    selected_units = st.sidebar.multiselect(
        "Units (national total shown if empty)", unit_options, key=f"{key_prefix}_units"
    )

    mask = df["year"].between(*year_range)
    filtered = df[mask]

    st.caption(
        f"{len(filtered):,} unit-month records across "
        f"{int(year_range[0])}-{int(year_range[1])}. {source_note}"
    )

    trend_source = filtered[filtered["unit_name"].isin(selected_units)] if selected_units else filtered[filtered["unit_name"] == "Total"]
    trend = trend_source.groupby("period", as_index=False)["total_cases"].sum()
    st.subheader("Total Cases Over Time" + (" (Selected Units)" if selected_units else " (National)"))
    fig = px.line(trend, x="period", y="total_cases", markers=True)
    fig.update_layout(xaxis_title="", yaxis_title="Total Cases")
    st.plotly_chart(fig, use_container_width=True)

    breakdown_source = filtered[filtered["unit_name"].isin(selected_units)] if selected_units else filtered[filtered["unit_name"] == "Total"]
    render_kpis(breakdown_source, filtered[filtered["unit_name"] == "Total"] if not selected_units else breakdown_source)
    render_breakdown_charts(breakdown_source)
    render_unit_comparison(filtered)
    render_data_table(filtered, f"bd_crime_{key_prefix}_filtered")


def annual_tab():
    df = load_annual()

    st.sidebar.header("Annual Filters")
    years = sorted(df["year"].unique())
    year_range = st.sidebar.select_slider(
        "Year range", options=years, value=(years[0], years[-1]), key="annual_years"
    )
    unit_options = sorted_units(df["unit_name"])
    selected_units = st.sidebar.multiselect(
        "Units (national total shown if empty)", unit_options, key="annual_units"
    )

    filtered = df[df["year"].between(*year_range)]
    st.caption(
        f"{len(filtered):,} unit-year records across {int(year_range[0])}-{int(year_range[1])} "
        "(scraped directly from HTML tables, no OCR involved)."
    )

    trend_source = filtered[filtered["unit_name"].isin(selected_units)] if selected_units else filtered[filtered["unit_name"] == "Total"]
    trend = trend_source.groupby("year", as_index=False)["total_cases"].sum()
    st.subheader("Total Cases Over Time" + (" (Selected Units)" if selected_units else " (National)"))
    fig = px.line(trend, x="year", y="total_cases", markers=True)
    fig.update_layout(xaxis_title="", yaxis_title="Total Cases")
    st.plotly_chart(fig, use_container_width=True)

    breakdown_source = filtered[filtered["unit_name"].isin(selected_units)] if selected_units else filtered[filtered["unit_name"] == "Total"]
    render_kpis(breakdown_source, filtered[filtered["unit_name"] == "Total"] if not selected_units else breakdown_source)
    render_breakdown_charts(breakdown_source)
    render_unit_comparison(filtered)
    render_data_table(filtered, "bd_crime_annual_filtered")


def main():
    st.set_page_config(page_title="Bangladesh Crime Statistics", layout="wide")
    st.title("Bangladesh Crime Statistics Dashboard")
    st.markdown(
        "Data automatically scraped and OCR'd from official "
        "[Bangladesh Police](https://www.police.gov.bd/) crime statistics reports."
    )

    tab1, tab2, tab3 = st.tabs([
        "Monthly (2019-Present)", "Monthly - PaddleOCR", "Annual (2010-2019)",
    ])
    with tab1:
        monthly_tab(
            DATA_DIR / "bd_crime_monthly_master.csv", "monthly",
            "Some cells are blank where scanned PDF reports could not be OCR'd "
            "reliably (see `data/blanks_review.csv`). OCR engine: macOS Vision.",
        )
    with tab2:
        st.caption(
            "Built entirely with [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) "
            "instead of the default Vision engine (see `scraper/pipeline_paddle.py`), "
            "kept as a separate dataset for side-by-side accuracy comparison."
        )
        monthly_tab(
            DATA_DIR / "bd_crime_monthly_master_paddle.csv", "paddle",
            "Some cells are blank where scanned PDF reports could not be OCR'd "
            "reliably (see `data/blanks_review_paddle.csv`). OCR engine: PaddleOCR.",
        )
    with tab3:
        annual_tab()


if __name__ == "__main__":
    main()
