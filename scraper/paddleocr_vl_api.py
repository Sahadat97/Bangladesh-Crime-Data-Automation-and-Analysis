"""Client for the hosted PaddleOCR-VL API (AI Studio serving).

Unlike the local paddleocr library (run_paddle_ocr in extract_pdf_table.py,
called once per rendered page image), this is an async job API: a whole PDF
is uploaded in one call, processed server-side across all its pages, and the
result is fetched as a JSONL file once the job finishes - so there's no
per-page image rendering or OpenCV grid detection involved on our end. Each
page's result is already parsed into markdown (including any tables), not
raw per-word bounding boxes.

Requires the PADDLEOCR_API_TOKEN environment variable (an AI Studio access
token) to be set.
"""
import json
import os
import time

import requests

JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
DEFAULT_MODEL = "PaddleOCR-VL-1.6"
DEFAULT_OPTIONAL_PAYLOAD = {
    "useDocOrientationClassify": False,
    "useDocUnwarping": False,
    "useChartRecognition": False,
}


def _auth_headers():
    token = os.environ.get("PADDLEOCR_API_TOKEN")
    if not token:
        raise RuntimeError(
            "PADDLEOCR_API_TOKEN is not set - export your AI Studio access "
            "token before using the paddleocr-api engine."
        )
    return {"Authorization": f"bearer {token}"}


def submit_job(file_path, model=DEFAULT_MODEL, optional_payload=None):
    """Uploads a local PDF/image file to the hosted API. Returns the jobId."""
    payload = optional_payload or DEFAULT_OPTIONAL_PAYLOAD
    data = {"model": model, "optionalPayload": json.dumps(payload)}
    with open(file_path, "rb") as f:
        resp = requests.post(JOB_URL, headers=_auth_headers(), data=data, files={"file": f})
    resp.raise_for_status()
    return resp.json()["data"]["jobId"]


def poll_job(job_id, poll_interval=5, timeout=1800):
    """Polls until the job finishes. Returns the result JSONL download URL."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{JOB_URL}/{job_id}", headers=_auth_headers())
        resp.raise_for_status()
        data = resp.json()["data"]
        state = data["state"]
        if state == "done":
            return data["resultUrl"]["jsonUrl"]
        if state == "failed":
            raise RuntimeError(f"PaddleOCR-VL job {job_id} failed: {data.get('errorMsg')}")
        time.sleep(poll_interval)
    raise TimeoutError(f"PaddleOCR-VL job {job_id} did not finish within {timeout}s")


def fetch_page_results(jsonl_url):
    """Downloads the job's JSONL result and returns a flat list of per-page
    layoutParsingResults dicts (one per page), each with a "markdown" key
    ({"text": ..., "images": {...}}).
    """
    resp = requests.get(jsonl_url)
    resp.raise_for_status()
    pages = []
    for line in resp.text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        result = json.loads(line)["result"]
        pages.extend(result["layoutParsingResults"])
    return pages


def run_ocr_pdf(file_path, model=DEFAULT_MODEL, optional_payload=None, poll_interval=5, timeout=1800):
    """Submits file_path (a local PDF/image), waits for completion, and
    returns the list of per-page layoutParsingResults dicts.
    """
    job_id = submit_job(file_path, model=model, optional_payload=optional_payload)
    jsonl_url = poll_job(job_id, poll_interval=poll_interval, timeout=timeout)
    return fetch_page_results(jsonl_url)
