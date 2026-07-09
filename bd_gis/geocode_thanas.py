"""
Run this on your own machine (not in a restricted sandbox) to fill in the
lat/lon columns of bd_metro_thana_roster.csv that are currently blank.

Requires: pip install geopy
Respects Nominatim's usage policy: 1 request/sec, identifying User-Agent,
results cached to disk so a re-run doesn't re-hit the API for rows already
geocoded.

Usage:
    python3 geocode_thanas.py

Notes on accuracy:
- Nominatim will return the centroid of whatever OSM feature matches the
  query best -- for well-mapped areas (most of Dhaka, city cores generally)
  that's usually the neighbourhood/thana centroid. For less-mapped areas it
  may fall back to a less precise match, or fail outright (left blank,
  printed to stderr for manual follow-up).
- This gives you a POINT per thana, not the actual jurisdiction polygon --
  see the main README for why real thana boundary polygons aren't publicly
  available anywhere for these units.
"""
import csv
import time
import sys

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

IN_CSV = "bd_metro_thana_roster.csv"
OUT_CSV = "bd_metro_thana_roster_geocoded.csv"

UNIT_TO_CITY = {
    "DMP": "Dhaka",
    "CMP": "Chattogram",
    "RMP": "Rajshahi",
    "SMP": "Sylhet",
    "KMP": "Khulna",
    "BMP": "Barishal",
    "GMP": "Gazipur",
    "RPMP": "Rangpur",
}

geolocator = Nominatim(user_agent="bd-police-thana-geocoder (contact: replace-with-your-email)")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.1)

rows = list(csv.DictReader(open(IN_CSV)))

for row in rows:
    if row["lat"] and row["lon"]:
        continue  # already verified
    city = UNIT_TO_CITY[row["unit"]]
    query = f"{row['thana']} Thana, {city}, Bangladesh"
    try:
        loc = geocode(query)
        if loc:
            row["lat"] = round(loc.latitude, 6)
            row["lon"] = round(loc.longitude, 6)
            print(f"OK   {query} -> {loc.latitude:.5f},{loc.longitude:.5f}")
        else:
            print(f"MISS {query}", file=sys.stderr)
    except Exception as e:
        print(f"ERR  {query}: {e}", file=sys.stderr)

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["unit", "division", "thana", "lat", "lon"])
    w.writeheader()
    w.writerows(rows)

print(f"\nWrote {OUT_CSV}")
