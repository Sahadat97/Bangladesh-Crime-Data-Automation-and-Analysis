# Bangladesh Police unit GIS data

Built 2026-07-08. No ready-made shapefile exists anywhere publicly for
Bangladesh Police's Range or Metropolitan Police jurisdictions, so this
was reconstructed from two independent parts.

## What's in here

**Ranges (real polygon boundaries, high confidence)**
- `bd_police_ranges.geojson` / `.shp` (+ .dbf/.shx/.prj/.cpg) - one polygon
  per Range (Dhaka, Chittagong, Rajshahi, Khulna, Sylhet, Barisal, Rangpur,
  Mymensingh), built by dissolving official district boundaries according to
  the district list published on each Range's own page at police.gov.bd.
- `bd_districts_with_range.geojson` - the 64 underlying district polygons,
  each tagged with its Range, for QA or finer-grained use.

Source geometry: geoBoundaries-derived ADM2 (district) polygons, via the
`bdatlas` npm package. Verified: all 64 Bangladesh districts are assigned to
exactly one Range, matching the counts stated on police.gov.bd (Dhaka 13,
Chittagong 11, Rajshahi 8, Khulna 10, Sylhet 4, Barisal 6, Rangpur 8,
Mymensingh 4). See `ranges_preview.png` for a rendered check.

One judgment call: the Dhaka Range page still lists Netrokona as one of its
districts, but Netrokona is also listed under Mymensingh Range (created
later, in 2015, by splitting off part of Dhaka Range). Netrokona was
assigned to Mymensingh Range here since that's the current structure and
resolves the count to exactly 64/64 districts with no double-counting.

**Metropolitan units (points + attributes only, NOT polygons)**
- `bd_metro_police_units.csv` and `bd_metro_police_points.geojson` - one row
  per unit (DMP, CMP, KMP, RMP, BMP, SMP, RPMP, GMP) with headquarters
  coordinates, official jurisdiction area in sq km (where police.gov.bd or
  Wikipedia states one), thana count, and the full thana list where
  published.

### Why no metro polygons

Metropolitan Police jurisdictions are defined by a named list of individual
police stations / thanas (e.g. DMP = 49 named thanas inside Dhaka city),
not by whole districts or upazilas. I checked every public source I could
reach:
- police.gov.bd's own unit pages (text-only, no boundary data)
- Bangladesh's official GIS portal (gis.gov.bd), LGED's GIS portal, BBS's
  GIS domain - all administrative boundaries only (division/district/
  upazila/union), no police layer
- HDX's official Bangladesh admin boundaries (COD-AB)
- npm packages `bdatlas`, `bd-geojson`, `bangladesh-geo-data`, `bd-geodata`,
  `@bangladeshi/bangladesh-address` - these carry thana *names* and hierarchy
  (bangladesh-geo-data lists 639 thanas) but none of them ship thana-level
  *polygon* geometry.

No dataset with real thana/ward boundary polygons is publicly available, so
a genuine metro-unit boundary shapefile isn't something I could build
without primary survey/cadastral data from Bangladesh Police, RAJUK, or the
relevant City Corporation - that would need to be requested directly from
those agencies.

## Regenerating / extending

- `build_ranges.py` - district -> Range crosswalk and dissolve logic
- `build_metro.py` - metro unit attribute table
- `districts_adm2.geojson` - raw 64-district source polygons (from bdatlas)

To add real metro boundaries later: replace the point geometries in
`build_metro.py` with actual thana polygons once/if a suitable source is
found (e.g. if Bangladesh Police or a City Corporation publishes one), and
dissolve by unit the same way `build_ranges.py` does for districts.
