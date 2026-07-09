# -*- coding: utf-8 -*-
"""
Builds an updated, verified metro-unit table plus a full thana-level roster
with division/zone grouping, using:
  1) The user-supplied "Metropolitan Police Jurisdictions of Bangladesh" brief
     (2026-07-09) as the primary source for division groupings and thana
     names.
  2) Wikipedia infoboxes for each force (fetched 2026-07-09) as an independent
     cross-check on thana counts and jurisdiction area -- this caught that
     RMP's official police.gov.bd page (scraped earlier) was stale: RMP
     expanded from 4 to 12 thanas and 203 to 900 sq km in Feb 2018, which
     Wikipedia confirms and the user's brief correctly reflects.
  3) Two thana-level coordinates verified directly against Wikipedia infoboxes
     (Gulshan, Dhanmondi). Everything else in `lat`/`lon` is left blank --
     no fabricated points. See README section "Geocoding the thana roster"
     for how to complete this properly.
"""
import csv
import geopandas as gpd
from shapely.geometry import Point

OUT_DIR = "/sessions/sleepy-vigilant-maxwell/mnt/outputs/bd_gis"

# ---------------------------------------------------------------------------
# Updated metro-unit summary (supersedes bd_metro_police_units.csv v1)
# ---------------------------------------------------------------------------
METRO_UNITS_V2 = [
    dict(unit="DMP", name="Dhaka Metropolitan Police", established="1976-02-01",
         area_sq_km=1600.0, num_thanas=50, num_divisions=8,
         city_corporations="DNCC, DSCC",
         area_source="https://en.wikipedia.org/wiki/Dhaka_Metropolitan_Police (verified)"),
    dict(unit="CMP", name="Chattogram Metropolitan Police", established="1978-11-30",
         area_sq_km=655.0, num_thanas=16, num_divisions=4,
         city_corporations="CCC",
         area_source="user brief; police.gov.bd states 304.66 sq km -- unresolved discrepancy, see README"),
    dict(unit="RMP", name="Rajshahi Metropolitan Police", established="1992-07-01",
         area_sq_km=900.0, num_thanas=12, num_divisions=4,
         city_corporations="RCC",
         area_source="https://en.wikipedia.org/wiki/Rajshahi_Metropolitan_Police (verified: Feb 2018 expansion, 4->12 thanas)"),
    dict(unit="SMP", name="Sylhet Metropolitan Police", established="2006",
         area_sq_km=518.0, num_thanas=6, num_divisions=2,
         city_corporations="SCC",
         area_source="user brief (not independently verified)"),
    dict(unit="KMP", name="Khulna Metropolitan Police", established="1986-07-01",
         area_sq_km=91.0, num_thanas=8, num_divisions=2,
         city_corporations="KCC",
         area_source="user brief; police.gov.bd states 70 sq km -- unresolved discrepancy, see README"),
    dict(unit="BMP", name="Barishal Metropolitan Police", established="2009",
         area_sq_km=137.0, num_thanas=4, num_divisions=1,
         city_corporations="BCC",
         area_source="user brief (not independently verified)"),
    dict(unit="GMP", name="Gazipur Metropolitan Police", established="2018",
         area_sq_km=320.0, num_thanas=8, num_divisions=1,
         city_corporations="GCC",
         area_source="user brief; Wikipedia/press give ~331.5 sq km (128 sq mi) -- close, within rounding"),
    dict(unit="RPMP", name="Rangpur Metropolitan Police", established="2018-09-16",
         area_sq_km=240.0, num_thanas=6, num_divisions=1,
         city_corporations="RpCC",
         area_source="https://en.wikipedia.org/wiki/Rangpur_Metropolitan_Police gives 239.72 sq km (verified, matches)"),
]

# ---------------------------------------------------------------------------
# Full thana roster with division/zone grouping (from the user's brief)
# lat/lon populated only where independently verified against a Wikipedia
# thana infobox; otherwise left blank.
# ---------------------------------------------------------------------------
VERIFIED_POINTS = {
    ("DMP", "Gulshan"): (23.7917, 90.4167),
    ("DMP", "Dhanmondi"): (23.7450, 90.3767),
}

THANAS = []

def add(unit, division, names):
    for n in names:
        lat, lon = VERIFIED_POINTS.get((unit, n), (None, None))
        THANAS.append(dict(unit=unit, division=division, thana=n, lat=lat, lon=lon))

# DMP -- 8 divisions x 6 thanas (48) per user brief, plus Bhashantek and
# Cantonment which the brief's own count of 50 implies but does not assign
# to a division; Wikipedia's DMP thana list confirms both exist and gives
# 50 as the current total, so they're added with division left unspecified.
add("DMP", "Mirpur", ["Mirpur", "Pallabi", "Shah Ali", "Kafrul", "Rupnagar", "Darus Salam"])
add("DMP", "Uttara", ["Uttara East", "Uttara West", "Turag", "Airport", "Dakshinkhan", "Uttarkhan"])
add("DMP", "Gulshan", ["Gulshan", "Banani", "Badda", "Bhatara", "Khilkhet", "Rampura"])
add("DMP", "Tejgaon", ["Tejgaon", "Tejgaon Industrial Area", "Hatirjheel", "Mohammadpur", "Adabor", "Sher-e-Bangla Nagar"])
add("DMP", "Ramna", ["Ramna", "Shahbagh", "New Market", "Dhanmondi", "Hazaribagh", "Kalabagan"])
add("DMP", "Motijheel", ["Motijheel", "Paltan", "Sabujbagh", "Khilgaon", "Mugda", "Shahjahanpur"])
add("DMP", "Wari", ["Wari", "Demra", "Jatrabari", "Shyampur", "Kadamtali", "Gendaria"])
add("DMP", "Lalbagh", ["Lalbagh", "Chawkbazar", "Kamrangirchar", "Kotwali", "Bangshal", "Sutrapur"])
add("DMP", "(unassigned in source -- confirmed to exist per Wikipedia)", ["Bhashantek", "Cantonment"])

# CMP -- 4 divisions x 4 thanas (16)
add("CMP", "North", ["Panchlaish", "Chandgaon", "Bayazid Bostami", "Khulshi"])
add("CMP", "South", ["Kotwali", "Bakalia", "Sadarghat", "Chawkbazar"])
add("CMP", "West", ["Double Mooring", "Halishahar", "Pahartali", "Akbar Shah"])
add("CMP", "Port", ["Bandar (Port)", "Patenga", "EPZ", "Karnaphuli"])

# RMP -- 4 divisions x 3 thanas (12)
add("RMP", "Boalia", ["Boalia", "Chandrima", "Rajpara"])
add("RMP", "Kasiadanga", ["Kasiadanga", "Karnahar", "Damkura"])
add("RMP", "Motihar", ["Motihar", "Katakhali", "Belpukur"])
add("RMP", "Shah Makhdum", ["Shah Makhdum", "Airport", "Paba"])

# SMP -- 2 divisions x 3 thanas (6)
add("SMP", "North", ["Kotwali", "Jalalabad", "Airport"])
add("SMP", "South", ["South Surma", "Moglabazar", "Shah Poran"])

# KMP -- 2 divisions x 4 thanas (8)
add("KMP", "South", ["Khulna Sadar", "Sonadanga", "Labanchara", "Harintana"])
add("KMP", "North", ["Khalishpur", "Daulatpur", "Khan Jahan Ali", "Aranghata"])

# BMP -- flat list, 4 thanas
add("BMP", None, ["Kotwali", "Kawnia", "Airport", "Bandar"])

# GMP -- flat list, 8 thanas
add("GMP", None, ["Tongi East", "Tongi West", "Gacha", "Basan", "Konabari",
                   "Kashimpur", "Joydebpur (Sadar)", "Pubail"])

# RPMP -- flat list, 6 thanas
add("RPMP", None, ["Kotwali", "Parshuram", "Tajhat", "Mahiganj", "Haragach", "Hazirhat"])

print(f"Total thana rows: {len(THANAS)}")
by_unit = {}
for t in THANAS:
    by_unit.setdefault(t["unit"], 0)
    by_unit[t["unit"]] += 1
print(by_unit)

# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------
with open(f"{OUT_DIR}/bd_metro_police_units_v2.csv", "w", newline="") as f:
    fieldnames = ["unit", "name", "established", "area_sq_km", "num_thanas",
                  "num_divisions", "city_corporations", "area_source"]
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for row in METRO_UNITS_V2:
        w.writerow(row)

with open(f"{OUT_DIR}/bd_metro_thana_roster.csv", "w", newline="") as f:
    fieldnames = ["unit", "division", "thana", "lat", "lon"]
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for row in THANAS:
        w.writerow(row)

# GeoJSON for the subset with verified coordinates
pts = [t for t in THANAS if t["lat"] is not None]
gdf = gpd.GeoDataFrame(
    pts,
    geometry=[Point(t["lon"], t["lat"]) for t in pts],
    crs="EPSG:4326",
)
gdf.to_file(f"{OUT_DIR}/bd_thana_points_verified.geojson", driver="GeoJSON")

print("Wrote bd_metro_police_units_v2.csv, bd_metro_thana_roster.csv, bd_thana_points_verified.geojson")
print(f"Verified coordinate points: {len(pts)} of {len(THANAS)}")
