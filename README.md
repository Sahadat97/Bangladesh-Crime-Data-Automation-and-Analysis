# Bangladesh Crime Data Automation and Analysis

An automated pipeline that scrapes crime statistics published by the
[Bangladesh Police](https://www.police.gov.bd/), extracts the tables from
scanned monthly reports, and consolidates everything into clean CSVs for
analysis.

## Data source

The Bangladesh Police publishes crime statistics broken down by unit
(metropolitan police, ranges, etc.) and crime type:

- **2010-2019**: available as real HTML tables (`crime_statistic/year/{year}`)
- **2019-present**: published monthly as scanned PDF reports (no text layer),
  listed on paginated announcement pages

## How it works

1. **`scrape_listing.py`** walks the paginated announcement listing and
   collects one record per monthly PDF report (title, month, year, download
   URL).
2. **`scrape_year_table.py`** pulls the older (2010-2019) annual tables
   directly from HTML — no OCR needed.
3. **`extract_pdf_table.py`** processes each scanned PDF page: extracts the
   embedded raster image, detects the table's grid lines with OpenCV, OCRs
   the page using macOS's Vision framework (via the compiled `ocr.swift`
   helper — more accurate than Tesseract on this scan quality), and maps
   each recognized token to its (row, column) cell using the grid geometry.
   Cells the OCR can't confidently read are left blank and logged for manual
   review rather than guessed.
4. **`pipeline.py`** ties it together end-to-end: downloads and caches PDFs,
   runs extraction, writes one CSV per month, and concatenates everything
   into a master table.

## Repository layout

```
scraper/
  scrape_listing.py       # discovers monthly PDF report URLs
  scrape_year_table.py    # scrapes 2010-2019 annual HTML tables
  extract_pdf_table.py    # OCR + table extraction from scanned PDFs
  pipeline.py             # end-to-end orchestration
  ocr.swift / build.sh    # macOS Vision-based OCR helper (compile with build.sh)
  bin/ocr                 # compiled OCR binary

data/
  pdfs/                   # cached source PDF downloads
  monthly_csv/            # one CSV per extracted month
  annual_2010_2019/       # per-year CSVs (2010-2019)
  bd_crime_annual_2010_2019.csv   # consolidated annual table (2010-2019)
  bd_crime_monthly_master.csv     # consolidated monthly table (2019-present)
  blanks_review.csv       # cells OCR couldn't read, for manual review
```

## Setup

```bash
pip3 install -r scraper/requirements.txt
./scraper/build.sh                 # compile the Vision OCR helper (macOS only)
```

## Usage

```bash
python3 scraper/pipeline.py
```

This downloads any new monthly PDFs, extracts their tables, and refreshes
`data/bd_crime_monthly_master.csv` and `data/blanks_review.csv`.
