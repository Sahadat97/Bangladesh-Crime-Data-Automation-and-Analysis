"""Same end-to-end pipeline as pipeline.py, but hardcoded to the PaddleOCR
engine and writing to separate *_paddle output paths - so running it never
overwrites the Vision-based reference dataset. Exists to produce a
PaddleOCR-built master dataset for comparison against the Vision one.
"""
from pathlib import Path

from pipeline import DATA_DIR, run

CSV_DIR_PADDLE = DATA_DIR / "monthly_csv_paddle"
MASTER_PATH_PADDLE = DATA_DIR / "bd_crime_monthly_master_paddle.csv"
BLANKS_PATH_PADDLE = DATA_DIR / "blanks_review_paddle.csv"


if __name__ == "__main__":
    run(
        engine="paddleocr",
        csv_dir=CSV_DIR_PADDLE,
        master_path=MASTER_PATH_PADDLE,
        blanks_path=BLANKS_PATH_PADDLE,
    )
