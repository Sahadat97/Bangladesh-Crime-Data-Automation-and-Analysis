"""Streamlit dashboard for Bangladesh Police crime statistics.

Reads data/bd_crime_monthly_master_paddle.csv - the dataset built entirely
by the hosted PaddleOCR-VL API (see scraper/pipeline_paddle.py) - and
presents it as an interactive dashboard: national/unit trends, crime-type
breakdowns, and a dedicated view for "recovery" cases (the r_* columns -
cases where police recovered arms, explosives, narcotics, or smuggled
goods, as opposed to cases filed).
"""
import json
import math
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DATA_DIR = Path(__file__).parent.parent / "data"
MASTER_PATH = DATA_DIR / "bd_crime_monthly_master_paddle.csv"
GIS_DIR = Path(__file__).parent.parent / "bd_gis"
RANGES_GEOJSON_PATH = GIS_DIR / "bd_police_ranges.geojson"
METRO_UNITS_PATH = GIS_DIR / "bd_metro_police_units.csv"

# The GIS source uses the older "Barisal Range" spelling (one "s"); the
# crime dataset uses the modern "Barishal Range" (two) - aliased here so the
# two datasets join on the same unit names.
RANGE_NAME_ALIAS = {"Barisal Range": "Barishal Range"}

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
def load_data(_mtime: float) -> pd.DataFrame:
    """2010-2018 only has one annual row per unit (scraped from HTML tables,
    no monthly breakdown available); 2019+ has monthly rows plus, for most
    years, its own Jan-Dec annual-total row too. `period` (a real calendar
    date) is only computed for genuine monthly rows - annual-only rows get
    NaT, since they can't be placed at a specific month.

    `_mtime` isn't used in the body - it's the CSV's modification time,
    passed in purely so Streamlit's cache key changes whenever the file is
    updated (e.g. by the monthly automation workflow). Without it, this
    function has no arguments at all, so the cache would never invalidate
    until the app process itself restarts.
    """
    df = pd.read_csv(MASTER_PATH)
    is_regular_month = df["month"].isin(MONTH_ORDER)
    df["period"] = pd.NaT
    df.loc[is_regular_month, "period"] = pd.to_datetime(
        df.loc[is_regular_month, "year"].astype(int).astype(str) + "-" + df.loc[is_regular_month, "month"],
        format="%Y-%B",
    )
    return df


@st.cache_data
def load_gis():
    """Ranges have real polygon boundaries (dissolved district boundaries);
    Metro units only have headquarters points, since no public source ships
    thana-level boundary polygons for them (see bd_gis/README.md). Railway
    Range and Total have no geometry at all and are excluded from the map.
    """
    with open(RANGES_GEOJSON_PATH) as f:
        ranges_geojson = json.load(f)
    for feature in ranges_geojson["features"]:
        name = feature["properties"]["range_name"]
        feature["properties"]["range_name"] = RANGE_NAME_ALIAS.get(name, name)

    metro = pd.read_csv(METRO_UNITS_PATH)
    return ranges_geojson, metro


DEFAULT_MAP_CENTER = {"lat": 23.8, "lon": 90.3}
DEFAULT_MAP_ZOOM = 5.3


def _flatten_coords(coords):
    """Yields every [lon, lat] pair out of a GeoJSON Polygon or MultiPolygon
    coordinates array, regardless of nesting depth.
    """
    if isinstance(coords[0], (int, float)):
        yield coords
    else:
        for c in coords:
            yield from _flatten_coords(c)


def compute_map_view(selected_units, ranges_geojson, metro):
    """Bounding box + zoom level covering just the selected units, so the
    map auto-zooms in on them instead of always showing the whole country.
    Falls back to the default full-country view when nothing is selected.
    """
    if not selected_units:
        return DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM

    range_by_name = {f["properties"]["range_name"]: f for f in ranges_geojson["features"]}
    lats, lons = [], []
    for unit in selected_units:
        feature = range_by_name.get(unit)
        if feature is not None:
            coords = list(_flatten_coords(feature["geometry"]["coordinates"]))
            lats += [c[1] for c in coords]
            lons += [c[0] for c in coords]
        metro_row = metro[metro["unit"] == unit]
        lats += metro_row["lat"].tolist()
        lons += metro_row["lon"].tolist()

    if not lats:
        return DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM

    # A single point (one Metro unit) has zero span, so floor it at ~city
    # scale rather than dividing by/logging zero. Slope and offset are
    # calibrated so the full-country span (~6 degrees) matches the default
    # zoom above.
    span = max(max(lats) - min(lats), max(lons) - min(lons), 0.08)
    zoom = max(5.0, min(8.4 - 1.2 * math.log2(span), 12.0))
    center = {"lat": (max(lats) + min(lats)) / 2, "lon": (max(lons) + min(lons)) / 2}
    return center, zoom


def render_crime_map(units_df: pd.DataFrame, selected_units: list[str]):
    st.subheader("Crime Map")
    ranges_geojson, metro = load_gis()

    unit_totals = units_df.groupby("unit_name")["total_cases"].sum()

    range_names = [f["properties"]["range_name"] for f in ranges_geojson["features"]]
    range_values = [unit_totals.get(name) for name in range_names]
    metro = metro.copy()
    metro["total_cases"] = metro["unit"].map(unit_totals)

    all_values = [v for v in range_values if v is not None] + metro["total_cases"].dropna().tolist()
    if not all_values:
        st.info("No data available for the current filters.")
        return
    vmin, vmax = min(all_values), max(all_values)

    fig = go.Figure()
    fig.add_trace(go.Choroplethmap(
        geojson=ranges_geojson,
        locations=range_names,
        z=range_values,
        featureidkey="properties.range_name",
        colorscale="Oranges",
        zmin=vmin, zmax=vmax,
        marker_opacity=0.7,
        marker_line_width=0.5,
        marker_line_color="#5F5E5A",
        colorbar_title="Cases",
        hovertemplate="<b>%{location}</b><br>Cases: %{z:,.0f}<extra></extra>",
        name="Ranges",
    ))

    sizes = metro["total_cases"].fillna(0)
    marker_sizes = 12 + 28 * (sizes / sizes.max()).pow(0.5) if sizes.max() else 12
    fig.add_trace(go.Scattermap(
        lat=metro["lat"], lon=metro["lon"],
        mode="markers",
        marker=dict(
            size=marker_sizes, color=metro["total_cases"],
            colorscale="Oranges", cmin=vmin, cmax=vmax,
            showscale=False,
        ),
        customdata=metro[["unit", "name", "total_cases"]],
        hovertemplate="<b>%{customdata[1]} (%{customdata[0]})</b><br>Cases: %{customdata[2]:,.0f}<extra></extra>",
        name="Metro units",
    ))

    center, zoom = compute_map_view(selected_units, ranges_geojson, metro)
    fig.update_layout(
        map=dict(style="carto-positron", center=center, zoom=zoom),
        margin=dict(l=0, r=0, t=0, b=0),
        height=520,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    missing = sorted(set(unit_totals.index) - set(range_names) - set(metro["unit"]) - {"Total"})
    if missing:
        st.caption(
            f"No boundary/location data available for: {', '.join(missing)} "
            "(not shown on the map - see `bd_gis/README.md`). Ranges are shaded "
            "polygons; Metropolitan Police units are markers sized and colored "
            "by case count."
        )


def dedupe_annual_vs_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """For each (unit_name, year), keeps the monthly rows if any exist for
    that year, otherwise keeps the single annual-total row. Without this, a
    year like 2020 - which has both 12 monthly rows and its own Jan-Dec
    annual-total row - would get double-counted in any sum over the full
    dataset; 2010-2018 has no monthly rows at all, so its annual row is the
    only data to keep.
    """
    monthly = df[~df["is_annual_total"]]
    annual_only = df[df["is_annual_total"]]
    covered = set(monthly[["unit_name", "year"]].apply(tuple, axis=1))
    annual_fallback = annual_only[~annual_only[["unit_name", "year"]].apply(tuple, axis=1).isin(covered)]
    return pd.concat([monthly, annual_fallback], ignore_index=True)


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
        fig.update_traces(hovertemplate="Cases: %{x:,}<extra></extra>")
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

    filter_cols = st.multiselect("Filter by column", df.columns.tolist())
    result = df
    for col in filter_cols:
        if pd.api.types.is_bool_dtype(df[col]):
            options = sorted(df[col].dropna().unique().tolist())
            chosen = st.multiselect(col, options, default=options)
            result = result[result[col].isin(chosen)]
        elif pd.api.types.is_numeric_dtype(df[col]):
            lo, hi = float(df[col].min()), float(df[col].max())
            if lo == hi:
                st.caption(f"{col}: only one value ({lo:g}) in the current selection")
                continue
            chosen_range = st.slider(col, lo, hi, (lo, hi))
            result = result[result[col].between(*chosen_range)]
        else:
            options = sorted(df[col].dropna().unique().tolist(), key=str)
            chosen = st.multiselect(col, options, default=options)
            result = result[result[col].isin(chosen)]

    st.dataframe(result, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered data as CSV",
        result.to_csv(index=False).encode("utf-8"),
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

    df = load_data(MASTER_PATH.stat().st_mtime)

    st.sidebar.header("Filters")
    years = sorted(df["year"].dropna().unique())
    year_range = st.sidebar.select_slider("Year range", options=years, value=(years[0], years[-1]))
    unit_options = sorted_units(df["unit_name"])
    selected_units = st.sidebar.multiselect("Units (national total shown if empty)", unit_options)
    selected_months = st.sidebar.multiselect("Months (all shown if empty)", MONTH_ORDER)

    filtered = df[df["year"].between(*year_range)]
    if selected_months:
        # A specific month only exists as a genuine monthly row - annual-only
        # rows (2010-2018, or a year's Jan-Dec summary) represent the whole
        # year and can't be attributed to one month, so they're excluded
        # entirely once a month filter is active.
        filtered = filtered[(~filtered["is_annual_total"]) & (filtered["month"].isin(selected_months))]
    else:
        filtered = dedupe_annual_vs_monthly(filtered)
    st.caption(f"{len(filtered):,} unit-period records across {int(year_range[0])}-{int(year_range[1])}.")

    scope = totals_scope(filtered, selected_units)
    units_only = filtered[filtered["unit_name"] != "Total"]

    st.subheader("Total Cases Over Time" + (" (Selected Units)" if selected_units else " (National)"))
    view = st.radio("View", ["Year", "Month"], horizontal=True)
    if view == "Year":
        trend = scope.groupby("year", as_index=False)["total_cases"].sum()
        fig = px.line(trend, x="year", y="total_cases", markers=True)
        fig.update_layout(xaxis_title="", yaxis_title="Total Cases")
        st.plotly_chart(fig, use_container_width=True)
    else:
        monthly_only = scope[~scope["is_annual_total"]]
        trend = monthly_only.groupby("period", as_index=False)["total_cases"].sum()
        if trend.empty:
            st.info("No monthly data available for the current filters.")
        else:
            fig = px.line(trend, x="period", y="total_cases", markers=True)
            fig.update_layout(xaxis_title="", yaxis_title="Total Cases")
            st.plotly_chart(fig, use_container_width=True)
        if year_range[0] < 2019:
            st.caption(
                "2010-2018 only had a yearly total published (no monthly "
                "breakdown exists for those years), so they don't appear here."
            )

    render_kpis(scope, units_only if not selected_units else scope)
    map_scope = units_only[units_only["unit_name"].isin(selected_units)] if selected_units else units_only
    render_crime_map(map_scope, selected_units)
    render_breakdown_charts(scope)
    render_unit_comparison(units_only)
    render_data_table(filtered)


if __name__ == "__main__":
    main()
