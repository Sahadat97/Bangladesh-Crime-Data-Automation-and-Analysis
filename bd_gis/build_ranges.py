import json
import geopandas as gpd

IN = "/sessions/sleepy-vigilant-maxwell/mnt/outputs/bd_gis/districts_adm2.geojson"
OUT_DIR = "/sessions/sleepy-vigilant-maxwell/mnt/outputs/bd_gis"

gdf = gpd.read_file(IN)
gdf["shapeName"] = gdf["shapeName"].str.strip()

# Crosswalk built from police.gov.bd's own Range pages (fetched 2026-07-08).
# Netrokona/Netrakona is assigned to Mymensingh Range (current structure),
# even though the Dhaka Range page (apparently stale) also lists it.
RANGE_DISTRICTS = {
    "Dhaka Range": [
        "Dhaka", "Narayanganj", "Gazipur", "Manikganj", "Munshiganj",
        "Narsingdi", "Tangail", "Kishoreganj", "Faridpur", "Gopalganj",
        "Madaripur", "Rajbari", "Shariatpur",
    ],
    "Chittagong Range": [
        "Chittagong", "Comilla", "Feni", "Chandpur", "Brahamanbaria",
        "Noakhali", "Lakshmipur", "Cox's Bazar", "Rangamati", "Bandarban",
        "Khagrachhari",
    ],
    "Rajshahi Range": [
        "Rajshahi", "Nawabganj", "Natore", "Naogaon", "Pabna",
        "Sirajganj", "Bogra", "Joypurhat",
    ],
    "Khulna Range": [
        "Khulna", "Bagerhat", "Satkhira", "Jessore", "Magura",
        "Jhenaidah", "Narail", "Kushtia", "Chuadanga", "Meherpur",
    ],
    "Sylhet Range": ["Sylhet", "Habiganj", "Sunamganj", "Maulvibazar"],
    "Barisal Range": [
        "Barisal", "Barguna", "Jhalokati", "Bhola", "Patuakhali", "Pirojpur",
    ],
    "Rangpur Range": [
        "Rangpur", "Nilphamari", "Lalmonirhat", "Dinajpur", "Panchagarh",
        "Thakurgaon", "Gaibandha", "Kurigram",
    ],
    "Mymensingh Range": ["Mymensingh", "Sherpur", "Jamalpur", "Netrakona"],
}

district_to_range = {}
for rng, districts in RANGE_DISTRICTS.items():
    for d in districts:
        district_to_range[d] = rng

all_bd_districts = set(gdf["shapeName"])
mapped = set(district_to_range.keys())

missing_in_map = sorted(all_bd_districts - mapped)
missing_in_gdf = sorted(mapped - all_bd_districts)
print("Districts in shapefile but NOT assigned to a range:", missing_in_map)
print("Districts in crosswalk but NOT found in shapefile (name mismatch):", missing_in_gdf)
assert not missing_in_map, "Every district must belong to exactly one range"
assert not missing_in_gdf, "Every crosswalk name must match the shapefile"

gdf["range_name"] = gdf["shapeName"].map(district_to_range)

# Sanity: district count per range
counts = gdf.groupby("range_name")["shapeName"].count()
print(counts)

dissolved = gdf.dissolve(by="range_name", as_index=False)
dissolved = dissolved[["range_name", "geometry"]]
dissolved["district_count"] = dissolved["range_name"].map(
    lambda r: len(RANGE_DISTRICTS[r])
)
dissolved["districts"] = dissolved["range_name"].map(
    lambda r: ", ".join(RANGE_DISTRICTS[r])
)

dissolved.to_file(f"{OUT_DIR}/bd_police_ranges.geojson", driver="GeoJSON")
dissolved.to_file(f"{OUT_DIR}/bd_police_ranges.shp")

# Also keep district-level file with range attribute, useful for QA / finer use
gdf.to_file(f"{OUT_DIR}/bd_districts_with_range.geojson", driver="GeoJSON")

print("Done. Ranges:", list(dissolved["range_name"]))
print("Total area check (deg^2, just sanity):", dissolved.geometry.area.sum())
