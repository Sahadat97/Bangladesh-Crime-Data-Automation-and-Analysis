"""Scrapes the Bangladesh Police 'Crime Statistics' announcement listing pages.

Each row on a listing page (e.g. https://www.police.gov.bd/en/january_2020?page=1)
links to one month's PDF report. This module walks the paginated listing and
returns one record per month: {title, month, year, upload_date, pdf_url}.
"""
import re
import requests
from bs4 import BeautifulSoup

LISTING_URL = "https://www.police.gov.bd/en/january_2020"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MONTH_RE = re.compile(r"Crime Statistics,\s*([A-Za-z]+)-?(\d{4})", re.IGNORECASE)


def fetch_listing_page(page: int):
    """Returns list of dicts for one listing page, or [] if the page has no rows."""
    resp = requests.get(LISTING_URL, params={"page": page}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table")
    if table is None:
        return []

    records = []
    for row in table.find("tbody").find_all("tr", recursive=False):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 5:
            continue

        title = cells[1].get_text(strip=True)
        issuing_authority = cells[2].get_text(strip=True)
        upload_date = cells[3].get_text(strip=True)

        download_link = None
        for a in row.find_all("a"):
            href = a.get("href", "")
            if href.lower().endswith(".pdf"):
                download_link = href
                break
        if download_link is None:
            continue

        m = MONTH_RE.search(title)
        month_name, year = (m.group(1), int(m.group(2))) if m else (None, None)

        records.append({
            "title": title,
            "month": month_name,
            "year": year,
            "issuing_authority": issuing_authority,
            "upload_date": upload_date,
            "pdf_url": download_link,
        })
    return records


def fetch_all_listings(max_pages=50):
    """Walks pages until an empty page is hit. Returns the combined record list."""
    all_records = []
    for page in range(1, max_pages + 1):
        records = fetch_listing_page(page)
        if not records:
            break
        all_records.extend(records)
    return all_records


if __name__ == "__main__":
    records = fetch_listing_page(1)
    print(f"Found {len(records)} entries on page 1")
    for r in records[:5]:
        print(r)
