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

## Update (2026-07-09): thana-level roster from a user-supplied brief

You sent a detailed "Metropolitan Police Jurisdictions of Bangladesh" brief
with per-division thana breakdowns for all 8 metro units. Before using it I
checked it against Wikipedia's infoboxes for each force, since a couple of
figures (DMP at 1,600 km², RMP at 900 km²) looked too large at first glance.
Both checked out: DMP's infobox confirms 1,600 km² / 50 stations exactly,
and RMP's confirms a February 2018 expansion from 4 to 12 stations and 203
to 900 km² -- police.gov.bd's own RMP page (used in the first pass of this
project) turned out to be stale, still showing the pre-2018 numbers. RPMP
and GMP also check out against Wikipedia (239.72 km² and ~331.5 km²
respectively, vs the brief's 240 and 320 -- within rounding).

Two figures in the brief did NOT match the police.gov.bd pages fetched
earlier in this project, and I could not resolve which is current:
- CMP area: brief says 655 km², police.gov.bd says 304.66 km²
- KMP area: brief says 91 km², police.gov.bd says 70 km²
Both are plausible if either force's jurisdiction was quietly expanded (as
happened with RMP) and police.gov.bd's page simply wasn't updated -- but I
have no independent confirmation either way. Treat these two area figures
as unverified until you can check a primary source (an RTI request, or the
individual force's own site).

New files from this pass:
- `bd_metro_police_units_v2.csv` -- corrected per-unit summary (current
  thana count, division count, verified/flagged area, city corporation).
- `bd_metro_thana_roster.csv` -- all 110 thanas across the 8 units, each
  tagged with its division/zone from the brief. `lat`/`lon` are populated
  for exactly 2 rows (Gulshan and Dhanmondi, DMP) where I independently
  verified coordinates against each thana's own Wikipedia infobox -- every
  other row is blank rather than guessed.
- `bd_thana_points_verified.geojson` -- just those 2 verified points.
- `geocode_thanas.py` -- a script to run on your own machine (not this
  sandbox) that fills in the remaining 108 coordinates via Nominatim,
  respecting its 1 req/sec usage policy. My sandbox's network is
  allowlisted and can't reach the Nominatim or Overpass APIs directly,
  which is why this step needs to happen on your end. Coverage won't be
  perfect -- not every thana has a well-mapped OSM entry -- but it'll get
  you real points for most of them; failures print to stderr for manual
  follow-up.

One gap worth flagging: the brief's DMP division breakdown lists 48 named
thanas across 8 divisions, but states 50 total. Wikipedia's DMP thana list
confirms 50 exist; the two missing from the brief's groupings are
Bhashantek and Cantonment. I added both to the roster under "unassigned in
source" rather than guessing which division they belong to.

## Update (2026-07-09): real Metro boundaries via City Corporation polygons

Found that HDX's official Bangladesh admin boundaries (COD-AB, ADM3 level -
https://data.humdata.org/dataset/cod-ab-bgd, fetched 2026-07-09) includes
City Corporations as their own polygon features - not part of the standard
division/district/upazila/union hierarchy checked in the original pass, so
it was missed then. Every one of the 8 Metro units' City Corporation(s) is
present, matching the `city_corporations` column already in
`bd_metro_police_units_v2.csv` exactly.

- `bd_metro_city_corporations.geojson` - one polygon per Metro unit
  (DMP's is a union of Dhaka North + South City Corporation; the other 7
  each match one ADM3 feature exactly).
- `build_metro_cc.py` - the extraction/union script. Its 37MB source file
  (`bgd_admin3.geojson`, from the HDX zip above) isn't checked in; download
  fresh to regenerate.

**Important caveat**: City Corporation limits are NOT the same as actual
police jurisdiction. They're consistently *smaller* than each unit's
published jurisdiction area in `bd_metro_police_units_v2.csv` - e.g. DMP's
two City Corporations sum to ~304 km² vs. its reported 1,600 km² - since
policing extends beyond the core municipal boundary into surrounding
areas. Both the City-Corporation area and the full jurisdiction area are
kept as separate properties on each feature so downstream consumers (the
Streamlit app's map hover) can show both rather than implying the shown
shape is the complete jurisdiction.

`bd_metro_police_points.geojson` and the original `bd_metro_police_units.csv`
(headquarters points only) are now superseded by this for mapping purposes,
but kept for their `lat`/`lon` headquarters coordinates and original source
citations.

## Regenerating / extending

- `build_ranges.py` - district -> Range crosswalk and dissolve logic
- `build_metro.py` - original metro unit attribute table (headquarters
  points; superseded for boundaries by `build_metro_cc.py` above)
- `build_metro_cc.py` - Metro unit City Corporation boundaries (see above)
- `build_thana_roster.py` - builds the 110-thana roster from the user brief
- `geocode_thanas.py` - fills in thana coordinates via Nominatim (run
  locally - this sandbox's network can't reach it)
- `districts_adm2.geojson` - raw 64-district source polygons (from bdatlas)

To get real thana-level (not City-Corporation-level) metro boundaries:
run `geocode_thanas.py` to get real points for the roster in
`bd_metro_thana_roster.csv`, then either dissolve a convex hull around each
unit's thana points, or search specifically for thana/ward-level polygons
on OpenStreetMap (not yet checked) as a closer approximation.
