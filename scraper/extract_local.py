"""Runs extraction over already-downloaded PDFs in data/pdfs/ - no network calls.

Use this instead of pipeline.py when the listing/download step is being slow or
rate-limited but the PDFs you need are already cached locally.
"""
from pathlib import Path

import pandas as pd

from extract_pdf_table import extract_pdf

DATA_DIR = Path(__file__).parent.parent / "data"
PDF_DIR = DATA_DIR / "pdfs"
CSV_DIR = DATA_DIR / "monthly_csv"


def slugify(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def run():
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    all_blanks = []
    all_frames = []

    pdf_paths = sorted(PDF_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_paths)} cached PDFs")

    for pdf_path in pdf_paths:
        print(f"Processing {pdf_path.name}")
        for page_index, df, blanks, month, year, is_annual in extract_pdf(pdf_path):
            if df is None:
                print(f"  page {page_index}: FAILED - {blanks}")
                all_blanks.append({
                    "source": pdf_path.name, "page": page_index,
                    "month": None, "year": None, "unit": "ENTIRE PAGE",
                    "column": "extraction failed", "note": blanks,
                })
                continue

            csv_name = f"{year}-{slugify(month)}.csv" if year else f"{pdf_path.stem}-p{page_index}.csv"
            csv_path = CSV_DIR / csv_name
            df.to_csv(csv_path, index=False)
            df["is_annual_total"] = is_annual
            df["source_pdf"] = pdf_path.name
            all_frames.append(df)

            for unit, col in blanks:
                all_blanks.append({
                    "source": pdf_path.name, "page": page_index,
                    "month": month, "year": year, "unit": unit, "column": col, "note": "",
                })
            print(f"  page {page_index}: {month} {year} -> {csv_path.name} ({len(blanks)} blanks)")

    if all_blanks:
        pd.DataFrame(all_blanks).to_csv(DATA_DIR / "blanks_review.csv", index=False)
        print(f"\n{len(all_blanks)} total blank cells logged to data/blanks_review.csv")

    if all_frames:
        master = pd.concat(all_frames, ignore_index=True)
        master.to_csv(DATA_DIR / "bd_crime_monthly_master.csv", index=False)
        print(f"Master table: {len(master)} rows -> data/bd_crime_monthly_master.csv")


if __name__ == "__main__":
    run()
