"""Builds bd_metro_city_corporations.geojson: one polygon per Metro Police
unit, taken from HDX's official Bangladesh admin boundaries (COD-AB, ADM3
level) rather than computed - DMP's is unioned from its two City
Corporations, the other 7 units each match exactly one ADM3 feature.

Source (not checked in - 37MB compressed, download fresh to regenerate):
https://data.humdata.org/dataset/cod-ab-bgd -> bgd_admin_boundaries.geojson.zip
-> bgd_admin3.geojson, fetched 2026-07-09.

Caveat: City Corporation limits are NOT the same as actual police
jurisdiction - they're consistently smaller than each unit's published
jurisdiction area in bd_metro_police_units_v2.csv (e.g. DMP's two City
Corporations sum to ~304 sq km vs. its reported 1,600 sq km), since
policing extends beyond the core municipal boundary into surrounding
areas. This is the urban core, not the full jurisdiction - both figures
are kept in the output properties so callers can be transparent about it.
"""
import json
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

with open("bgd_admin3.geojson") as f:
    admin3 = json.load(f)

by_name = {f["properties"]["adm3_name"]: f for f in admin3["features"]}

UNIT_CC = {
    "DMP": ["Dhaka North City Corporation", "Dhaka South City Corporation"],
    "CMP": ["Chattogram City Corporation"],
    "RMP": ["Rajshahi City Corporation"],
    "SMP": ["Sylhet City Corporation"],
    "KMP": ["Khulna City Corporation"],
    "BMP": ["Barishal City Corporation"],
    "GMP": ["Gazipur City Corporation"],
    "RPMP": ["Rangpur City Corporation"],
}

features = []
for unit, cc_names in UNIT_CC.items():
    shapes = []
    total_area = 0.0
    for cc_name in cc_names:
        feat = by_name[cc_name]
        shapes.append(shape(feat["geometry"]))
        total_area += feat["properties"]["area_sqkm"]
    geom = unary_union(shapes) if len(shapes) > 1 else shapes[0]
    features.append({
        "type": "Feature",
        "properties": {
            "unit": unit,
            "city_corporations": ", ".join(cc_names),
            "cc_area_sq_km": round(total_area, 2),
        },
        "geometry": mapping(geom),
    })

out = {"type": "FeatureCollection", "features": features}
with open("bd_metro_city_corporations.geojson", "w") as f:
    json.dump(out, f)

for feat in features:
    p = feat["properties"]
    print(p["unit"], "->", p["city_corporations"], "| area:", p["cc_area_sq_km"], "sq km")
