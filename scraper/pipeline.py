"""End-to-end pipeline: listing pages -> PDFs -> extracted monthly tables.

Downloads are cached in data/pdfs/ and re-used on subsequent runs. For each
page extracted, writes one CSV to data/monthly_csv/, appends any blank cells
to data/blanks_review.csv (for manual completion against the source PDF), and
finally concatenates everything into data/bd_crime_monthly_master.csv.
"""
import re
from pathlib import Path

import pandas as pd
import requests

from extract_pdf_table import extract_pdf
from scrape_listing import fetch_all_listings

DATA_DIR = Path(__file__).parent.parent / "data"
PDF_DIR = DATA_DIR / "pdfs"
CSV_DIR = DATA_DIR / "monthly_csv"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def slugify_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def infer_caption(entry, pdf_path, page_index, n_pages, month, year, is_annual):
    """Recovers month/year/is_annual when the OCR engine couldn't read a page's
    "Crime Statistics in <Month> <Year>" caption (happens occasionally - e.g.
    PaddleOCR misses it on faint scans). Annual-bundle PDFs always lay out 12
    monthly pages followed by one Jan-Dec total page, in that fixed order,
    regardless of scan quality - so a missing caption there can be inferred
    from page position. Single-report PDFs fall back to the month/year already
    parsed from the listing page's title by scrape_listing.
    """
    if month is not None:
        return month, year, is_annual
    if n_pages == 13:
        m = re.search(r"(\d{4})", pdf_path.stem)
        inferred_year = int(m.group(1)) if m else entry.get("year")
        if page_index < 12:
            return MONTH_NAMES[page_index], inferred_year, False
        if page_index == 12:
            return "January-December", inferred_year, True
    if entry.get("month") and entry.get("year"):
        return entry["month"], entry["year"], False
    return month, year, is_annual


def download_pdf(url: str, dest: Path, attempts: int = 3):
    if dest.exists():
        return
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            # (connect timeout, read timeout) - caps how long one stalled request can block the run
            resp = requests.get(url, headers=HEADERS, timeout=(10, 30))
            resp.raise_for_status()
            tmp = dest.with_suffix(".part")
            tmp.write_bytes(resp.content)
            tmp.rename(dest)
            return
        except requests.exceptions.RequestException as e:
            last_error = e
            print(f"    attempt {attempt}/{attempts} failed: {e}")
    raise last_error


def run(engine="vision", csv_dir=CSV_DIR, master_path=None, blanks_path=None):
    """csv_dir/master_path/blanks_path default to the standard (Vision) output
    locations, but can be overridden so an alternate engine's pass doesn't
    overwrite the reference dataset - see pipeline_paddle.py.
    """
    master_path = master_path or (DATA_DIR / "bd_crime_monthly_master.csv")
    blanks_path = blanks_path or (DATA_DIR / "blanks_review.csv")

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    csv_dir.mkdir(parents=True, exist_ok=True)

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

        print(f"Processing {entry['title']} ({pdf_path.name})")
        pages = extract_pdf(pdf_path, engine)
        for page_index, df, blanks, month, year, is_annual in pages:
            if df is None:
                print(f"  page {page_index}: FAILED - {blanks}")
                all_blanks.append({
                    "source": entry["title"], "page": page_index,
                    "month": None, "year": None, "unit": "ENTIRE PAGE",
                    "column": "extraction failed", "note": blanks,
                })
                continue

            month, year, is_annual = infer_caption(entry, pdf_path, page_index, len(pages), month, year, is_annual)
            df["month"] = month
            df["year"] = year
            label = f"{month} {year}"
            csv_name = f"{year}-{slugify_title(str(month))}.csv" if year else f"{pdf_path.stem}-p{page_index}.csv"
            csv_path = csv_dir / csv_name
            df.to_csv(csv_path, index=False)
            df["is_annual_total"] = is_annual
            df["source_pdf"] = pdf_path.name
            all_frames.append(df)

            for unit, col in blanks:
                all_blanks.append({
                    "source": entry["title"], "page": page_index,
                    "month": month, "year": year, "unit": unit, "column": col, "note": "",
                })
            print(f"  page {page_index}: {label} -> {csv_path.name} ({len(blanks)} blanks)")

    if all_blanks:
        pd.DataFrame(all_blanks).to_csv(blanks_path, index=False)
        print(f"\n{len(all_blanks)} total blank cells logged to {blanks_path}")

    if all_frames:
        master = pd.concat(all_frames, ignore_index=True)
        master.to_csv(master_path, index=False)
        print(f"Master table: {len(master)} rows -> {master_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--engine", choices=["vision", "paddleocr"], default="vision",
        help="OCR backend for reading scanned PDF pages (default: vision)",
    )
    args = parser.parse_args()
    run(args.engine)
