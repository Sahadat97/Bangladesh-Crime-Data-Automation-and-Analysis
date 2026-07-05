"""Streamlit dashboard for Bangladesh Police crime statistics.

Reads data/bd_crime_monthly_master_paddle.csv - the dataset built entirely
by the hosted PaddleOCR-VL API (see scraper/pipeline_paddle.py) - and
presents it as an interactive dashboard: national/unit trends, crime-type
breakdowns, and a dedicated view for "recovery" cases (the r_* columns -
cases where police recovered arms, explosives, narcotics, or smuggled
goods, as opposed to cases filed).
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_DIR = Path(__file__).parent.parent / "data"
MASTER_PATH = DATA_DIR / "bd_crime_monthly_master_paddle.csv"

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
    "DMP", "CMP", "KMP", "RMP", "BMP", "SMP", "RPMP", "GMP",
    "Dhaka Range", "Mymensingh Range", "Chittagong Range", "Sylhet Range",
    "Khulna Range", "Barishal Range", "Rajshahi Range",
    "Rangpur Range", "Railway Range",
]

MONTH_ORDER = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@st.cache_data
def load_monthly() -> pd.DataFrame:
    df = pd.read_csv(MASTER_PATH)
    df = df[~df["is_annual_total"]]  # exclude the Jan-Dec total page - a duplicate of the year, not a 13th month
    df["month"] = pd.Categorical(df["month"], categories=MONTH_ORDER, ordered=True)
    df["period"] = pd.to_datetime(
        df["year"].astype(int).astype(str) + "-" + df["month"].astype(str), format="%Y-%B", errors="coerce"
    )
    return df


def sorted_units(units: pd.Series) -> list[str]:
    present = list(units.dropna().unique())
    ordered = [u for u in UNIT_ORDER if u in present]
    ordered += sorted(u for u in present if u not in UNIT_ORDER and u != "Total")
    if "Total" in present:
        ordered.append("Total")
    return ordered


def totals_scope(filtered: pd.DataFrame, selected_units: list[str]) -> pd.DataFrame:
    """Rows to sum for the headline KPIs, trend line, and crime/recovery
    breakdowns. When specific units are picked, that's their rows; otherwise
    it's the dataset's own "Total" row directly - trustworthy to match
    exactly, now that the PaddleOCR-VL dataset has zero blank cells.
    """
    if selected_units:
        return filtered[filtered["unit_name"].isin(selected_units)]
    return filtered[filtered["unit_name"] == "Total"]


def render_kpis(totals_df: pd.DataFrame, units_df: pd.DataFrame):
    """totals_df drives the summed numbers (matches the Total row when
    unfiltered); units_df is always individual (non-Total) unit rows, since
    ranking the highest-crime unit needs real per-unit data regardless of
    what totals_df represents.
    """
    total_cases = totals_df["total_cases"].sum()
    total_recovery = totals_df["total_recovery_cases"].sum()
    top_crime_col = totals_df[list(CRIME_COLUMNS)].sum().idxmax() if not totals_df.empty else None
    top_unit = units_df.groupby("unit_name")["total_cases"].sum().idxmax() if not units_df.empty else "N/A"

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


def render_data_table(df: pd.DataFrame):
    st.subheader("Raw Data")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered data as CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name="bd_crime_monthly_paddle_filtered.csv",
        mime="text/csv",
    )


def main():
    st.set_page_config(page_title="Bangladesh Crime Statistics", layout="wide")
    st.title("Bangladesh Crime Statistics Dashboard")
    st.markdown(
        "Data automatically scraped from official "
        "[Bangladesh Police](https://www.police.gov.bd/) crime statistics reports "
        "and extracted with the hosted [PaddleOCR-VL](https://paddleocr.ai/) API "
        "(see `scraper/pipeline_paddle.py`)."
    )

    df = load_monthly()

    st.sidebar.header("Filters")
    years = sorted(df["year"].dropna().unique())
    year_range = st.sidebar.select_slider("Year range", options=years, value=(years[0], years[-1]))
    unit_options = sorted_units(df["unit_name"])
    selected_units = st.sidebar.multiselect("Units (national total shown if empty)", unit_options)

    filtered = df[df["year"].between(*year_range)]
    st.caption(f"{len(filtered):,} unit-month records across {int(year_range[0])}-{int(year_range[1])}.")

    scope = totals_scope(filtered, selected_units)
    units_only = filtered[filtered["unit_name"] != "Total"]

    trend = scope.groupby("period", as_index=False)["total_cases"].sum()
    st.subheader("Total Cases Over Time" + (" (Selected Units)" if selected_units else " (National)"))
    fig = px.line(trend, x="period", y="total_cases", markers=True)
    fig.update_layout(xaxis_title="", yaxis_title="Total Cases")
    st.plotly_chart(fig, use_container_width=True)

    render_kpis(scope, units_only if not selected_units else scope)
    render_breakdown_charts(scope)
    render_unit_comparison(filtered)
    render_data_table(filtered)


if __name__ == "__main__":
    main()
