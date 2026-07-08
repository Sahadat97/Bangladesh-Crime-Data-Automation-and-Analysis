import json
import geopandas as gpd
from shapely.geometry import Point

OUT_DIR = "/sessions/sleepy-vigilant-maxwell/mnt/outputs/bd_gis"

# All figures below were pulled directly from each unit's page on
# police.gov.bd (fetched 2026-07-08), cross-checked against Wikipedia for
# RPMP/GMP (whose police.gov.bd pages currently carry no descriptive text).
# NOTE: these are HEADQUARTERS POINTS with the officially stated
# jurisdiction area as an attribute -- NOT true polygon boundaries.
# No public source publishes thana/ward-level boundary polygons for these
# units (see README for details), so a real boundary shapefile is not
# achievable without primary survey data from Bangladesh Police / RAJUK-style
# city planning authorities.
METRO_UNITS = [
    {
        "unit": "DMP", "name": "Dhaka Metropolitan Police",
        "district": "Dhaka", "lat": 23.7115253, "lon": 90.4111451,
        "established": "1976-02-01", "num_thanas": 49,
        "area_sq_km": None,
        "thanas": "Adabor, Airport, Badda, Banani, Bangshal, Bhashantek, "
                  "Cantonment, Chackbazar, Darussalam, Dakshinkhan, Demra, "
                  "Dhanmondi, Gandaria, Gulshan, Hazaribag, Jatrabari, "
                  "Kadamtoli, Kafrul, Kalabagan, Kamrangirchar, Khilgaon, "
                  "Khilkhet, Kotwali, Lalbag, Mirpur Model, Mohammadpur, "
                  "Motijheel, Mugda, New Market, Pallabi, Paltan Model, "
                  "Ramna Model, Rampura, Rupnagar, Sabujbag, Shah Ali, "
                  "Shahbag, Sherebanglanagar, Shyampur, Sutrapur, "
                  "Shahjahanpur, Tejgaon, Tejgaon I/A, Turag, Uttara Model, "
                  "Uttarkhan, Uttara West, Vatara, Wari",
        "source": "https://www.police.gov.bd/en/dhaka_metropolitan_police",
    },
    {
        "unit": "CMP", "name": "Chittagong Metropolitan Police",
        "district": "Chittagong", "lat": 22.335109, "lon": 91.834073,
        "established": "1978-11-30", "num_thanas": 16,
        "area_sq_km": 304.66,
        "thanas": "Kotwali, Chandgaon, Panchlaish, Doublemooring, "
                  "Pahartali, Bandar, Baijid Bostami, Hali Shohor, "
                  "Kornafuli, Potenga, Bakolia, Akborsha, Shodhorgat, EPZ, "
                  "Chokbazar, Kulshi",
        "source": "https://www.police.gov.bd/en/chittagong_metropolitan_police",
    },
    {
        "unit": "KMP", "name": "Khulna Metropolitan Police",
        "district": "Khulna", "lat": 22.815774, "lon": 89.568679,
        "established": "1986-07-01", "num_thanas": 8,
        "area_sq_km": 70.0,
        "thanas": "Khulna Sadar, Sonadangha, Khalishpur, Daulatpur, "
                  "Khanjahan Ali, Labanchora, Horintana, Aranghata",
        "source": "https://www.police.gov.bd/en/khulna_metropolitan_police",
    },
    {
        "unit": "RMP", "name": "Rajshahi Metropolitan Police",
        "district": "Rajshahi", "lat": 24.3745, "lon": 88.6042,
        "established": "1992-07-01", "num_thanas": 4,
        "area_sq_km": 203.0,
        "thanas": "Boalia Model, Rajpara, Motihar, Shahmokhdum",
        "source": "https://www.police.gov.bd/en/rajshahi_metropolitan_police",
    },
    {
        "unit": "BMP", "name": "Barisal Metropolitan Police",
        "district": "Barisal", "lat": 22.7010, "lon": 90.3535,
        "established": "2006-10-26", "num_thanas": 4,
        "area_sq_km": None,
        "thanas": "Kotowali Model, Airport, Kawnia, Bondor",
        "source": "https://www.police.gov.bd/en/barisal_metropolitan_police",
    },
    {
        "unit": "SMP", "name": "Sylhet Metropolitan Police",
        "district": "Sylhet", "lat": 24.8897956, "lon": 91.8697894,
        "established": "2009-03", "num_thanas": 6,
        "area_sq_km": None,
        "thanas": "Kotwali, South Surma, Jalalabad, Airport, Moglabazar, "
                  "Hazrat Shah Paran",
        "source": "https://www.police.gov.bd/en/sylhet_metropolitan_police",
    },
    {
        "unit": "RPMP", "name": "Rangpur Metropolitan Police",
        "district": "Rangpur", "lat": 25.7558096, "lon": 89.244462,
        "established": "2018-09-16", "num_thanas": 6,
        "area_sq_km": 239.72,
        "thanas": "Kotwali, Haragach (full list of 6 not published on "
                  "police.gov.bd or Wikipedia as of 2026-07-08)",
        "source": "https://en.wikipedia.org/wiki/Rangpur_Metropolitan_Police",
    },
    {
        "unit": "GMP", "name": "Gazipur Metropolitan Police",
        "district": "Gazipur", "lat": 24.0022858, "lon": 90.4264283,
        "established": "2018", "num_thanas": 8,
        "area_sq_km": 331.5,
        "thanas": "Gazipur Sadar, Tongi East, Tongi West, Gacha, Bason, "
                  "Konabari, Kashimpur, Pubail",
        "source": "https://en.wikipedia.org/wiki/Gazipur_Metropolitan_Police",
    },
]

gdf = gpd.GeoDataFrame(
    METRO_UNITS,
    geometry=[Point(u["lon"], u["lat"]) for u in METRO_UNITS],
    crs="EPSG:4326",
)
gdf.to_file(f"{OUT_DIR}/bd_metro_police_points.geojson", driver="GeoJSON")

import csv
with open(f"{OUT_DIR}/bd_metro_police_units.csv", "w", newline="") as f:
    fieldnames = ["unit", "name", "district", "lat", "lon", "established",
                  "num_thanas", "area_sq_km", "thanas", "source"]
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for row in METRO_UNITS:
        w.writerow(row)

print("Wrote metro points GeoJSON and CSV for", len(METRO_UNITS), "units")
