"""Extracts crime-statistics tables from scanned Bangladesh Police PDFs.

These PDFs are scanned images with no text layer, so the pipeline per page is:
pull the embedded raster out of the PDF page -> detect the table's grid lines
with OpenCV -> OCR the page -> map each recognized token to its (row, col)
cell using the grid geometry, and read the "Crime Statistics in <Month> <Year>"
caption to label the page.

The OCR step is pluggable (see run_ocr/OCR_ENGINES below):
  - "vision" (default): macOS's Vision framework, via the compiled ocr.swift
    helper - far more accurate than Tesseract on this scan quality, tested
    empirically.
  - "paddleocr": PaddleOCR, a cross-platform alternative (useful off macOS,
    or to compare accuracy against Vision). Requires the optional
    paddleocr/paddlepaddle packages - see scraper/requirements-paddleocr.txt.

Some PDFs are a single month (one page); others ("annual" reports) bundle all
12 months of a year plus a Jan-Dec total, one page each, in the same layout -
so every PDF is processed page by page rather than assuming one page = one PDF.

Any cell Vision fails to read is left blank and reported so it can be filled in
by eye from the PDF - this scan quality does not support fully unattended OCR.
"""
import itertools
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pdfplumber

SCRAPER_DIR = Path(__file__).parent
OCR_BIN = SCRAPER_DIR / "bin" / "ocr"

UNITS = [
    "DMP", "CMP", "KMP", "RMP", "BMP", "SMP", "RPMP", "GMP",
    "Dhaka Range", "Mymensingh Range", "Chittagong Range", "Sylhet Range",
    "Khulna Range", "Barishal Range", "Rajshahi Range", "Rangpur Range",
    "Railway Range", "Total",
]

COLUMNS = [
    "unit_name", "dacoity", "robbery", "murder", "speedy_trial", "riot",
    "woman_child_repression", "kidnapping", "police_assault", "burglary",
    "theft", "other_cases", "r_arms_act", "r_explosive_act", "r_narcotics",
    "r_smuggling", "total_recovery_cases", "total_cases",
]

TITLE_RE = re.compile(
    r"Crime Statist\w*\s+in\s+([A-Za-z]+)(?:-([A-Za-z]+))?\s+(\d{4})", re.IGNORECASE
)


def _largest_image(page):
    """Some pages carry a small second image (e.g. a stamp); keep the table scan."""
    images = page.images
    if not images:
        raise ValueError("No embedded image found on this page")
    return max(images, key=lambda im: im["width"] * im["height"])


def extract_page_image(page):
    """Pulls the embedded scan out of a pdfplumber page as a BGR OpenCV image."""
    raw = _largest_image(page)["stream"].get_data()
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode embedded image")
    return img


def _cluster(vals, gap=8):
    vals = sorted(vals)
    if not vals:
        return []
    clusters = [[vals[0]]]
    for v in vals[1:]:
        if v - clusters[-1][-1] <= gap:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [int(np.mean(c)) for c in clusters]


# Row/column proportions calibrated from a manually-verified page (May 2026).
# Every page uses the same government spreadsheet template, so when raw line
# detection finds extra spurious lines (common - stray ink/noise, and this
# template's narrow "Riot" column has a genuinely small gap that fools a
# naive smallest-gap merge), we pick whichever subset of the detected lines
# best matches these reference proportions via least-squares fit, rather than
# guessing which lines to merge.
_REF_HLINES = [198, 241, 316, 374, 432, 491, 550, 610, 669, 729, 788, 845, 905, 964, 1023, 1082, 1141, 1200, 1258, 1318, 1377]
_REF_VLINES = [90, 350, 456, 579, 682, 792, 861, 1008, 1167, 1278, 1398, 1484, 1594, 1673, 1806, 1942, 2086, 2181, 2299]


def _best_fit_subset(lines, target, ref):
    """If `lines` has more than `target` points, finds the `target`-sized subset
    whose positions (after an affine fit) best match the reference proportions.
    """
    lines = sorted(lines)
    excess = len(lines) - target
    if excess == 0:
        return lines
    if excess < 0 or excess > 3:
        raise ValueError(f"Expected ~{target} grid lines, found {len(lines)} - inspect manually.")

    ref = np.array(ref, dtype=float)
    ref_frac = (ref - ref[0]) / (ref[-1] - ref[0])

    best_subset, best_err = None, None
    for combo in itertools.combinations(range(len(lines)), target):
        subset = np.array([lines[i] for i in combo], dtype=float)
        # least-squares affine fit: subset ~= a * ref_frac + b
        A = np.vstack([ref_frac, np.ones_like(ref_frac)]).T
        (a, b), residuals, *_ = np.linalg.lstsq(A, subset, rcond=None)
        fitted = a * ref_frac + b
        err = np.sum((fitted - subset) ** 2)
        if best_err is None or err < best_err:
            best_err, best_subset = err, subset

    return [round(x) for x in best_subset]


def _detect_lines_at_least(sums, span, target):
    """Tries progressively lower density thresholds until >= target lines are found
    (scan contrast varies enough between PDFs that a single fixed ratio misses lines
    on some pages, e.g. faint row borders).
    """
    lines = []
    for ratio in (0.2, 0.15, 0.1, 0.08, 0.05, 0.03, 0.02, 0.01):
        lines = _cluster(np.where(sums > span * ratio)[0])
        if len(lines) >= target:
            return lines
    return lines


def _lines_from_bw(bw, axis, target, divisors):
    """Tries a handful of morphology kernel sizes (in addition to threshold ratios)
    and keeps whichever gives the most lines, capped at succeeding early once
    `target` is reached. `axis` is 'h' or 'v'.
    """
    best = []
    for div in divisors:
        if axis == "h":
            size = max(bw.shape[1] // div, 5)
            morph = cv2.dilate(cv2.erode(bw, cv2.getStructuringElement(cv2.MORPH_RECT, (size, 1))),
                                cv2.getStructuringElement(cv2.MORPH_RECT, (size, 1)))
            sums, span = morph.sum(axis=1) / 255, morph.shape[1]
        else:
            size = max(bw.shape[0] // div, 5)
            morph = cv2.dilate(cv2.erode(bw, cv2.getStructuringElement(cv2.MORPH_RECT, (1, size))),
                                cv2.getStructuringElement(cv2.MORPH_RECT, (1, size)))
            sums, span = morph.sum(axis=0) / 255, morph.shape[0]

        lines = _detect_lines_at_least(sums, span, target)
        if len(lines) >= target:
            return lines
        if len(lines) > len(best):
            best = lines
    return best


def detect_grid(gray, n_rows_expected=21, n_cols_expected=19):
    """Finds the table's horizontal/vertical grid line positions via morphology.

    Falls back to CLAHE contrast enhancement + alternate kernel sizes for faint
    scans (e.g. old multi-generation photocopies) where standard Otsu thresholding
    under-detects row/column borders.
    """
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    hlines = _lines_from_bw(bw, "h", n_rows_expected, divisors=(40,))
    vlines = _lines_from_bw(bw, "v", n_cols_expected, divisors=(40,))

    if len(hlines) < n_rows_expected or len(vlines) < n_cols_expected:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray_eq = clahe.apply(gray)
        _, bw_eq = cv2.threshold(gray_eq, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        if len(hlines) < n_rows_expected:
            hlines = _lines_from_bw(bw_eq, "h", n_rows_expected, divisors=(100, 120, 80, 60))
        if len(vlines) < n_cols_expected:
            vlines = _lines_from_bw(bw_eq, "v", n_cols_expected, divisors=(40, 60, 80))

    if len(hlines) < n_rows_expected or len(vlines) < n_cols_expected:
        raise ValueError(
            f"Grid detection found too few lines (hlines={len(hlines)}, vlines={len(vlines)}, "
            f"expected {n_rows_expected}/{n_cols_expected}) - the scan may be cropped or skewed "
            "differently; inspect it manually."
        )

    hlines = _best_fit_subset(hlines, n_rows_expected, _REF_HLINES)
    vlines = _best_fit_subset(vlines, n_cols_expected, _REF_VLINES)
    return hlines, vlines


def detect_grid_with_rotation(image):
    """Every reference page is landscape (width > height). Some scans were saved
    sideways as portrait pages with the table rotated 90 inside them - line-count
    matching alone can't reliably tell which way is "up" (a rectangle's line
    structure is rotation-symmetric, and Vision can even OCR sideways text well
    enough to pass a caption check), so orientation is decided directly from the
    page's aspect ratio: portrait pages only ever try the two 90 rotations that
    make them landscape, never their original orientation.
    """
    h, w = image.shape[:2]
    if w >= h:
        candidates = [image]
    else:
        candidates = [
            cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE),
            cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE),
        ]

    last_error = None
    results = []
    for candidate in candidates:
        gray = cv2.cvtColor(candidate, cv2.COLOR_BGR2GRAY)
        try:
            hlines, vlines = detect_grid(gray)
            results.append((candidate, hlines, vlines))
        except ValueError as e:
            last_error = e
    if not results:
        raise last_error
    return results


def run_vision_ocr(image_path):
    """Calls the compiled Swift/Vision helper. Returns list of (text, cx, cy) in pixels."""
    if not OCR_BIN.exists():
        raise FileNotFoundError(f"{OCR_BIN} not found - run scraper/build.sh first")

    out = subprocess.run([str(OCR_BIN), str(image_path)], capture_output=True, text=True, check=True)
    img = cv2.imread(str(image_path))
    H, W = img.shape[:2]

    tokens = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 5:
            continue
        text, x, y, w, h = parts
        x, y, w, h = float(x), float(y), float(w), float(h)
        cx = (x + w / 2) * W
        cy_top = (1 - y - h / 2) * H  # Vision's origin is bottom-left; flip to top-left
        tokens.append((text, cx, cy_top))
    return tokens


_PADDLE_OCR = None


def _paddle_engine():
    """Lazily creates (and caches) the PaddleOCR engine - construction loads
    detection/recognition models from disk, so it's built once per process
    rather than per page/cell. Import is deferred here too: paddleocr and its
    paddlepaddle dependency are optional and heavy, only needed by callers
    that actually pass engine="paddleocr".
    """
    global _PADDLE_OCR
    if _PADDLE_OCR is None:
        from paddleocr import PaddleOCR
        _PADDLE_OCR = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    return _PADDLE_OCR


def run_paddle_ocr(image_path):
    """Runs PaddleOCR on the page image. Same (text, cx, cy) pixel-coordinate
    return shape as run_vision_ocr, so it's a drop-in alternative OCR backend -
    build_table/retry_blank_cells don't need to know which engine produced the
    tokens.
    """
    results = _paddle_engine().predict(str(image_path))
    tokens = []
    for result in results:
        for text, box in zip(result["rec_texts"], result["rec_boxes"]):
            x0, y0, x1, y1 = box
            tokens.append((text, (float(x0) + float(x1)) / 2, (float(y0) + float(y1)) / 2))
    return tokens


OCR_ENGINES = {
    "vision": run_vision_ocr,
    "paddleocr": run_paddle_ocr,
}


def run_ocr(image_path, engine="vision"):
    try:
        engine_fn = OCR_ENGINES[engine]
    except KeyError:
        raise ValueError(f"Unknown OCR engine {engine!r}; choose from {sorted(OCR_ENGINES)}")
    return engine_fn(image_path)


def parse_caption(tokens):
    """Reads the '<Month> <Year>' or '<Month>-<Month> <Year>' caption above the table."""
    for text, _, _ in tokens:
        m = TITLE_RE.search(text)
        if m:
            start_month, end_month, year = m.groups()
            is_range = end_month is not None
            label = f"{start_month}-{end_month}" if is_range else start_month
            return label, int(year), is_range
    return None, None, False


def _bucket(v, bounds):
    for i, (a, b) in enumerate(bounds):
        if a <= v < b:
            return i
    return None


def build_table(hlines, vlines, tokens):
    """Maps OCR tokens onto the grid. Returns (rows_of_cells, blank (r,c) indices,
    row_bounds, col_bounds) - the bounds let a caller re-crop specific blank cells.
    """
    row_bounds = list(zip(hlines[2:], hlines[3:]))   # skip the 2 header rows
    col_bounds = list(zip(vlines[:-1], vlines[1:]))

    grid = {}
    for text, cx, cy in tokens:
        r = _bucket(cy, row_bounds)
        c = _bucket(cx, col_bounds)
        if r is not None and c is not None:
            grid.setdefault((r, c), []).append((cx, text))

    rows, blank_idx = [], []
    for r in range(len(row_bounds)):
        row_vals = []
        for c in range(len(col_bounds)):
            cell = sorted(grid.get((r, c), []))
            value = " ".join(t for _, t in cell)
            row_vals.append(value)
            if not value and c > 0:  # unit-name column (c=0) is never blank
                blank_idx.append((r, c))
        rows.append(row_vals)
    return rows, blank_idx, row_bounds, col_bounds


def retry_blank_cells(image, row_bounds, col_bounds, rows, blank_idx, tmp_dir, page_index, engine="vision"):
    """Re-OCRs blank cells in isolation, which recognizes far better than a whole
    busy table page since there's no surrounding text to compete with - but a
    separate OCR subprocess call per cell doesn't scale (startup overhead per
    call dominates once a page has dozens of blanks). Instead, every blank cell
    for this page is upscaled and packed into one montage image, OCR'd in a
    single call, and results are mapped back by position. Fills `rows` in place;
    returns the (r, c) indices still blank afterward.
    """
    if not blank_idx:
        return []

    scale, gap = 4, 12
    crops = []
    for r, c in blank_idx:
        y0, y1 = row_bounds[r]
        x0, x1 = col_bounds[c]
        pad = 3
        crop = image[y0 + pad:y1 - pad, x0 + pad:x1 - pad]
        if crop.size == 0:
            crops.append(None)
            continue
        crops.append(cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC))

    max_row_width = 2200
    placements = []  # (r, c, x0, y0, x1, y1)
    x, y, row_h = gap, gap, 0
    for (r, c), crop in zip(blank_idx, crops):
        if crop is None:
            continue
        h, w = crop.shape[:2]
        if x + w + gap > max_row_width:
            x = gap
            y += row_h + gap
            row_h = 0
        placements.append((r, c, x, y, x + w, y + h, crop))
        row_h = max(row_h, h)
        x += w + gap

    montage_w = max_row_width
    montage_h = y + row_h + gap
    montage = np.full((montage_h, montage_w, 3), 255, dtype=np.uint8)
    for r, c, x0, y0, x1, y1, crop in placements:
        montage[y0:y1, x0:x1] = crop

    tmp_png = tmp_dir / f"_blanks_page{page_index}.png"
    cv2.imwrite(str(tmp_png), montage)
    try:
        tokens = run_ocr(tmp_png, engine)
    finally:
        tmp_png.unlink(missing_ok=True)

    still_blank = []
    for r, c, x0, y0, x1, y1, _ in placements:
        cell_tokens = [(t, cx, cy) for t, cx, cy in tokens if x0 <= cx < x1 and y0 <= cy < y1]
        text = "".join(t for t, _, _ in sorted(cell_tokens, key=lambda tok: tok[1]) if t.strip())
        if text.isdigit():
            rows[r][c] = text
        else:
            still_blank.append((r, c))

    # crops that failed to even produce a placement (empty region)
    placed = {(r, c) for r, c, *_ in placements}
    for r, c in blank_idx:
        if (r, c) not in placed:
            still_blank.append((r, c))
    return still_blank


def to_dataframe(rows, month, year):
    df = pd.DataFrame(rows, columns=COLUMNS)
    numeric_cols = [c for c in COLUMNS if c != "unit_name"]
    df[numeric_cols] = df[numeric_cols].apply(lambda s: pd.to_numeric(s, errors="coerce"))
    df["unit_name"] = UNITS[: len(df)]
    df["month"] = month
    df["year"] = year
    return df


def _ocr_candidate(image, page_index, tmp_dir, engine="vision"):
    tmp_png = tmp_dir / f"_page{page_index}.png"
    cv2.imwrite(str(tmp_png), image)
    try:
        return run_ocr(tmp_png, engine)
    finally:
        tmp_png.unlink(missing_ok=True)


def extract_page(page, page_index, tmp_dir, engine="vision"):
    """One page -> (DataFrame, blanks, month_label, year, is_annual_total)."""
    raw_image = extract_page_image(page)
    candidates = detect_grid_with_rotation(raw_image)

    # Grid line-counts can match on more than one rotation; only a rotation whose
    # OCR'd caption actually parses proves the content reads right-side-up.
    fallback = None
    for image, hlines, vlines in candidates:
        tokens = _ocr_candidate(image, page_index, tmp_dir, engine)
        month, year, is_annual = parse_caption(tokens)
        if month is not None:
            break
        if fallback is None:
            fallback = (image, hlines, vlines, tokens, month, year, is_annual)
    else:
        image, hlines, vlines, tokens, month, year, is_annual = fallback

    rows, blank_idx, row_bounds, col_bounds = build_table(hlines, vlines, tokens)
    blank_idx = retry_blank_cells(image, row_bounds, col_bounds, rows, blank_idx, tmp_dir, page_index, engine)
    df = to_dataframe(rows, month, year)

    # A cell can be non-empty (so build_table doesn't flag it as blank) yet still
    # fail to parse as a number - e.g. OCR misreads a digit as a letter. That must
    # not become a silent NaN: anything to_numeric coerced gets reported too.
    blank_set = set(blank_idx)
    numeric_cols = [c for c in COLUMNS if c != "unit_name"]
    for r in range(len(rows)):
        for c, col_name in enumerate(COLUMNS):
            if c == 0 or (r, c) in blank_set:
                continue
            if pd.isna(df.iloc[r][col_name]):
                blank_set.add((r, c))

    blanks = [(UNITS[r] if r < len(UNITS) else f"row{r}", COLUMNS[c]) for r, c in sorted(blank_set)]
    return df, blanks, month, year, is_annual


def extract_pdf(pdf_path, engine="vision"):
    """Every page of the PDF -> list of (DataFrame, blanks, month, year, is_annual)."""
    pdf_path = Path(pdf_path)
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            try:
                results.append((i, *extract_page(page, i, pdf_path.parent, engine)))
            except Exception as e:
                results.append((i, None, [(f"PAGE {i}", str(e))], None, None, False))
    return results


if __name__ == "__main__":
    import sys
    pdf_path = sys.argv[1]
    engine = sys.argv[2] if len(sys.argv) > 2 else "vision"
    for i, df, blanks, month, year, is_annual in extract_pdf(pdf_path, engine):
        label = f"{month} {year}" + (" (annual total)" if is_annual else "")
        print(f"\n=== page {i}: {label} ===")
        if df is None:
            print("FAILED:", blanks)
            continue
        print(df.to_string())
        print(f"{len(blanks)} cell(s) need manual review: {blanks}")
