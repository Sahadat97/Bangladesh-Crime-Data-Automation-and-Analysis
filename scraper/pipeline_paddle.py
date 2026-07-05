"""Builds the PaddleOCR-based master dataset, writing to separate *_paddle
output paths so it never overwrites the Vision-based reference dataset.

Default mode calls the hosted PaddleOCR-VL API (see paddleocr_vl_api.py):
one job submission processes a whole PDF (all its pages) server-side and
returns each page already parsed into markdown - with tables embedded as
raw HTML <table> markup, not pipe syntax - so this does NOT reuse
extract_pdf_table.py's per-page-image OpenCV grid detection. Instead, known
unit-name rows are matched directly out of each page's parsed HTML table.
Requires the PADDLEOCR_API_TOKEN environment variable (an AI Studio access
token).

`--engine local` instead runs the original path: the paddleocr Python
library locally, per page, through extract_pdf_table.py's grid-detection
pipeline (same as before this API was added).
"""
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from extract_pdf_table import COLUMNS, TITLE_RE, UNITS
from paddleocr_vl_api import run_ocr_pdf
from pipeline import DATA_DIR, PDF_DIR, download_pdf, infer_caption, run, slugify_title
from scrape_listing import fetch_all_listings

CSV_DIR_PADDLE = DATA_DIR / "monthly_csv_paddle"
MASTER_PATH_PADDLE = DATA_DIR / "bd_crime_monthly_master_paddle.csv"
BLANKS_PATH_PADDLE = DATA_DIR / "blanks_review_paddle.csv"


def build_page_dataframe(markdown_text):
    """Matches known unit-name rows (order-independent) out of the page's
    parsed HTML table and maps their cells onto our standard COLUMNS layout
    positionally. Header cells (with rowspan/colspan, e.g. "Recovery Cases"
    spanning 5 sub-columns) aren't reliable enough to key off of, but the
    unit names and column order are a fixed government template across the
    whole dataset - the same assumption the local OCR+grid pipeline relies
    on, and header rows simply won't match any unit name so they're skipped.
    """
    unit_lookup = {u.lower(): u for u in UNITS}
    # The source scans occasionally have "Ralway Range" (a genuine typo in
    # the government template, confirmed by inspecting the raw parsed table)
    # instead of "Railway Range" - without this alias the row reads fine but
    # fails our unit match and silently looks like a dropped/missing row.
    unit_lookup["ralway range"] = "Railway Range"
    n_numeric_cols = len(COLUMNS) - 1
    matched = {}

    soup = BeautifulSoup(markdown_text, "html.parser")
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if not cells:
                continue
            unit = unit_lookup.get(cells[0].strip().lower())
            if unit is None:
                continue
            values = cells[1:1 + n_numeric_cols]
            values += [""] * (n_numeric_cols - len(values))
            matched[unit] = values

    if not matched:
        return None
    # Any unit the layout parser dropped/merged entirely (not just a blank
    # cell within a matched row) gets a fully-blank row here, so it still
    # shows up as reported blanks below rather than silently vanishing, and
    # every page has the same fixed 18-row shape as the rest of the dataset.
    rows_out = [[unit] + matched.get(unit, [""] * n_numeric_cols) for unit in UNITS]
    df = pd.DataFrame(rows_out, columns=COLUMNS)
    numeric_cols = [c for c in COLUMNS if c != "unit_name"]
    df[numeric_cols] = df[numeric_cols].apply(lambda s: pd.to_numeric(s, errors="coerce"))
    return df


def parse_caption(markdown_text):
    m = TITLE_RE.search(markdown_text)
    if not m:
        return None, None, False
    start_month, end_month, year = m.groups()
    is_range = end_month is not None
    label = f"{start_month}-{end_month}" if is_range else start_month
    return label, int(year), is_range


def run_api():
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    CSV_DIR_PADDLE.mkdir(parents=True, exist_ok=True)

    listings = fetch_all_listings()
    print(f"Found {len(listings)} listing entries")

    all_blanks = []
    all_frames = []

    for entry in listings:
        pdf_path = PDF_DIR / f"{slugify_title(entry['title'])}.pdf"
        try:
            download_pdf(entry["pdf_url"], pdf_path)
        except Exception as e:
            print(f"  [download FAILED] {entry['title']}: {e}")
            continue

        print(f"Processing {entry['title']} ({pdf_path.name}) via PaddleOCR-VL API")
        try:
            pages = run_ocr_pdf(pdf_path)
        except Exception as e:
            print(f"  [API FAILED] {entry['title']}: {e}")
            all_blanks.append({
                "source": entry["title"], "page": None,
                "month": None, "year": None, "unit": "ENTIRE FILE",
                "column": "API call failed", "note": str(e),
            })
            continue

        n_pages = len(pages)
        for page_index, res in enumerate(pages):
            markdown_text = res.get("markdown", {}).get("text", "")
            month, year, is_annual = parse_caption(markdown_text)
            df = build_page_dataframe(markdown_text)
            if df is None:
                print(f"  page {page_index}: FAILED - no unit rows matched in markdown table")
                all_blanks.append({
                    "source": entry["title"], "page": page_index,
                    "month": None, "year": None, "unit": "ENTIRE PAGE",
                    "column": "extraction failed", "note": "no matching unit rows in markdown table",
                })
                continue

            month, year, is_annual = infer_caption(entry, pdf_path, page_index, n_pages, month, year, is_annual)
            df["month"] = month
            df["year"] = year

            label = f"{month} {year}"
            csv_name = f"{year}-{slugify_title(str(month))}.csv" if year else f"{pdf_path.stem}-p{page_index}.csv"
            csv_path = CSV_DIR_PADDLE / csv_name
            df.to_csv(csv_path, index=False)
            df["is_annual_total"] = is_annual
            df["source_pdf"] = pdf_path.name
            all_frames.append(df)

            numeric_cols = [c for c in COLUMNS if c != "unit_name"]
            blanks_in_page = 0
            for _, row in df.iterrows():
                for col in numeric_cols:
                    if pd.isna(row[col]):
                        all_blanks.append({
                            "source": entry["title"], "page": page_index,
                            "month": month, "year": year, "unit": row["unit_name"],
                            "column": col, "note": "",
                        })
                        blanks_in_page += 1
            print(f"  page {page_index}: {label} -> {csv_path.name} ({blanks_in_page} blanks)")

    if all_blanks:
        pd.DataFrame(all_blanks).to_csv(BLANKS_PATH_PADDLE, index=False)
        print(f"\n{len(all_blanks)} total blank cells logged to {BLANKS_PATH_PADDLE}")

    if all_frames:
        master = pd.concat(all_frames, ignore_index=True)
        master.to_csv(MASTER_PATH_PADDLE, index=False)
        print(f"Master table: {len(master)} rows -> {MASTER_PATH_PADDLE}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--engine", choices=["api", "local"], default="api",
        help="'api' (default) uses the hosted PaddleOCR-VL API; "
             "'local' uses the paddleocr Python library, per page (original behavior).",
    )
    args = parser.parse_args()

    if args.engine == "local":
        run(
            engine="paddleocr",
            csv_dir=CSV_DIR_PADDLE,
            master_path=MASTER_PATH_PADDLE,
            blanks_path=BLANKS_PATH_PADDLE,
        )
    else:
        run_api()
