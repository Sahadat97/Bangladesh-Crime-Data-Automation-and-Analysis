"""Scrapes the annual crime-statistics tables for years with no monthly PDF
(2010-2019), e.g. https://www.police.gov.bd/en/crime_statistic/year/2011.

Unlike the 2019+ monthly PDFs, these are real HTML tables - no OCR needed.
Same 18-column layout as the PDF extractor (Unit Name + 11 crime-type columns
+ 5 recovery-case sub-columns + Total Cases), but the unit list itself differs
from the modern PDFs: it includes an "ATU" unit not seen after 2019, and
spells it "Barisal Range" (one 's') rather than "Barishal Range".
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd

URL_TEMPLATE = "https://www.police.gov.bd/en/crime_statistic/year/{year}"
HEADERS = {"User-Agent": "Mozilla/5.0"}

COLUMNS = [
    "unit_name", "dacoity", "robbery", "murder", "speedy_trial", "riot",
    "woman_child_repression", "kidnapping", "police_assault", "burglary",
    "theft", "other_cases", "r_arms_act", "r_explosive_act", "r_narcotics",
    "r_smuggling", "total_recovery_cases", "total_cases",
]


def fetch_year_table(year: int) -> pd.DataFrame:
    resp = requests.get(URL_TEMPLATE.format(year=year), headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table")
    if table is None:
        raise ValueError(f"No table found for year {year}")

    tbody = table.find("tbody")
    rows = []
    for tr in tbody.find_all("tr", recursive=False):
        tds = tr.find_all("td", recursive=False)
        if len(tds) != len(COLUMNS):
            continue
        rows.append([td.get_text(strip=True) for td in tds])

    if not rows:
        raise ValueError(f"No data rows found for year {year}")

    df = pd.DataFrame(rows, columns=COLUMNS)
    numeric_cols = [c for c in COLUMNS if c != "unit_name"]
    df[numeric_cols] = df[numeric_cols].apply(lambda s: pd.to_numeric(s, errors="coerce"))
    df["year"] = year
    return df


if __name__ == "__main__":
    import sys
    year = int(sys.argv[1])
    df = fetch_year_table(year)
    print(df.to_string())
