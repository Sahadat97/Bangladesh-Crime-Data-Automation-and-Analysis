# Bangladesh Crime Data Automation and Analysis

An automated pipeline that scrapes crime statistics published by the
[Bangladesh Police](https://www.police.gov.bd/), extracts the tables from
scanned monthly reports, and consolidates everything into clean CSVs for
analysis.

**Live dashboard:** [bangladesh-crime-data-automation-and-analysis-bvphgl452h7man7k.streamlit.app](https://bangladesh-crime-data-automation-and-analysis-bvphgl452h7man7k.streamlit.app)

<p align="center">
  <img src="docs/pipeline-diagram.svg" alt="Bangladesh crime data automation pipeline: monthly PDF reports from the Bangladesh Police website trigger a scheduled GitHub Actions job, which uses the PaddleOCR-VL API to extract new tables into the master dataset, auto-updating the live Streamlit dashboard." width="480">
</p>

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
   the page, and maps each recognized token to its (row, column) cell using
   the grid geometry. Cells the OCR can't confidently read are left blank and
   logged for manual review rather than guessed. The OCR backend is
   pluggable:
   - `vision` (default): macOS's Vision framework, via the compiled
     `ocr.swift` helper — more accurate than Tesseract on this scan quality,
     tested empirically.
   - `paddleocr`: [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR), a
     cross-platform alternative (useful off macOS, or to compare accuracy
     against Vision). Install with
     `pip3 install -r scraper/requirements-paddleocr.txt`, then pass
     `--engine paddleocr` to `pipeline.py`, or `engine="paddleocr"` to
     `extract_pdf()`/`extract_page()` directly.
4. **`pipeline.py`** ties it together end-to-end: downloads and caches PDFs,
   runs extraction, writes one CSV per month, and concatenates everything
   into a master table.
5. **`pipeline_paddle.py`** builds a separate PaddleOCR-based master dataset
   (`data/bd_crime_monthly_master_paddle.csv`, kept apart from the Vision
   dataset for comparison). By default it uses the hosted
   [PaddleOCR-VL](https://paddleocr.ai/) API (`paddleocr_vl_api.py`): one
   job submission processes a whole PDF server-side and returns each page
   already parsed into markdown (tables as HTML), so known unit-name rows
   are matched directly out of each page's parsed table rather than going
   through `extract_pdf_table.py`'s OpenCV grid detection. This needs the
   `PADDLEOCR_API_TOKEN` environment variable set to an AI Studio access
   token. Pass `--engine local` instead to use the paddleocr Python library
   locally, per page (the original approach, via `extract_pdf_table.py`).

   This API path initially left some cells blank (a systematic gap where the
   "Railway Range" row was dropped on ~40% of pages, plus one isolated
   stray blank), all since resolved - see `data/blanks_review_paddle.csv`
   for the audit trail. The current `bd_crime_monthly_master_paddle.csv` has
   zero blank cells across all 1,728 rows.

   `run_api()` is incremental: any PDF whose filename already appears in
   the master's `source_pdf` column is skipped (no download, no API call),
   so re-running it only processes genuinely new months.

## Automation

`.github/workflows/monthly_update.yml` runs `pipeline_paddle.py` on a
schedule (a few times during the 1st-15th of each month, since the police
site publishes on no fixed day within that window) and commits any new
rows back to `main`. Requires a `PADDLEOCR_API_TOKEN` repository secret.
Since the pipeline is incremental, a run where nothing new has been
published yet does no OCR work. The Streamlit Cloud app auto-redeploys
whenever new data is pushed.

## Dashboard

**`app/app.py`** is a [Streamlit](https://streamlit.io/) dashboard for
exploring the consolidated data: national/unit trends over time, a crime-type
breakdown, and a dedicated recovery-cases view. Columns prefixed `r_`
(`r_arms_act`, `r_explosive_act`, `r_narcotics`, `r_smuggling`) are
**recovery cases** — arms, explosives, narcotics, or smuggled goods
recovered by police — as distinct from the filed criminal case counts in
the other columns. It has three tabs: the Vision-based monthly dataset, the
PaddleOCR-based monthly dataset (for side-by-side accuracy comparison), and
the 2010-2019 annual dataset.

Live at [bangladesh-crime-data-automation-and-analysis-bvphgl452h7man7k.streamlit.app](https://bangladesh-crime-data-automation-and-analysis-bvphgl452h7man7k.streamlit.app),
or run it locally:

```bash
pip3 install -r app/requirements.txt
streamlit run app/app.py
```

## Repository layout

```
scraper/
  scrape_listing.py       # discovers monthly PDF report URLs
  scrape_year_table.py    # scrapes 2010-2019 annual HTML tables
  extract_pdf_table.py    # OCR + table extraction from scanned PDFs
  pipeline.py             # end-to-end orchestration
  ocr.swift / build.sh    # macOS Vision-based OCR helper (compile with build.sh)
  bin/ocr                 # compiled OCR binary
  requirements-paddleocr.txt  # optional deps for the paddleocr engine

app/
  app.py                  # Streamlit dashboard
  requirements.txt        # dashboard dependencies

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
python3 scraper/pipeline.py                    # OCRs scanned pages with Vision (default)
python3 scraper/pipeline.py --engine paddleocr  # OCRs scanned pages with PaddleOCR instead
```

This downloads any new monthly PDFs, extracts their tables, and refreshes
`data/bd_crime_monthly_master.csv` and `data/blanks_review.csv`.
