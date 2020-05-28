Future version

- Added support for bigBed files
- Update readme installation instructions and troubleshooting instructions for macOS 10.15
- Always consider proxy headers (X-Forwarded-Host, X-Forwarded-Proto) for redirect URL construction
- Added support for server-side aggregation of multivec tiles by sending a `POST` request to the `/tiles` endpoint, where the body contains a JSON object mapping tileset UIDs to objects with properties `agg_groups` (a 2D array where each subarray is a group of rows to aggregate) and `agg_func` (the name of an aggregation function).

v1.13.0

- Add support from cooler v2 files for the fragments API

v1.12.0

- Added support for BAM files

v1.11.2

- Check for the existence of a viewconf before creating the link

v1.11.1

- Switch to using networkidle0

v1.11.0

- Link unfurling endpoints /link and /thumbnail
- **BREAKING CHANGE:** You need at least Python `v3.6` or higher

v1.10.2

- Added project to the admin interface
- coordSystem2 is no longer a required field

v1.10.1

- Check to make sure project's owner is not None before returning username

v1.10.0

- Added support for mrmatrix files
- Small bug fix for 500 available-chrom-sizes

v1.9.2

- Fixed STATIC_URL settings must end with a slash bug

v1.9.1

- Added support for the APP_BASEPATH setting

v1.7.? (????-??-??)

- Snippets API now allows limiting the size of snippets via `config.json`

v1.7.3 (2018-07-12)

- Return datatype along with tileset info

v1.7.0

- Merged all of Fritz's changes

v1.6.0 (2018-05-07)

- Start factoring out hgtiles code

v1.5.3 (2018-01-

- Refactored the chromsizes code to be more modular

v1.5.2 (2017-12-15)

- Catch error in fetching cached tiles and continue working

v1.5.1 (2017-12-14)

- Decode slugid in ingest command
- Resolve datapath in chromsizes

v1.5.0 (2017-12-05)

- Added support for cooler-based chrom-sizes retrieval
- Added support for beddb headers
- Upgraded do django 2.0

v1.4.2 (2017-11-13)

- Fixed issue where bigWig files weren't being found

v1.4.1 (2017-11-11)

- Built a fixed build

v1.4.0 (2017-11-08)

- Added support for bigWig files

v1.3.1 (2017-10-??)

- Fixed a bug with ignore-diags in the fragments API (again)

v1.3.1 (2017-11-02

- Serve static files from `hgs-static`

v1.3.0 (2017-10-21)

- Support arbitrary resolution cooler files
- Combine tile requests for beddb and bed2ddb files
- Increase width of higlassVersion field in the ViewConfModel to 16

v1.2.3 (2017-10-03)

- Same changes as last time. They didn't actually make it into v1.2.2
v1.2.2 (2017-10-03)

- Fixed a bug with ignore-diags in the fragments API

v1.2.1 (2017-08-30)

- Fixed an out-of-bounds error

v1.2.0 (2017-08-29)

- Group cooler tile requests so they can be retrieved more quickly

v1.1.3 (2017-08-14)

- Fix retrieval of snippets starting at negative positions
- Return 400 error for unsupported request bodies

v1.1.2 (2017-08-08)

- Return the created field as part of the serializer

v1.1.1 (2017-08-08)

- Introduced case insensitive ordering

v1.1.0 (2017-07-26)

- Extend endpoint for retrieval of normalized domains
- Retrieve complete snippets (and not just the upper triangle)
- Add option to balance the fragment endpoint
- Add percentage-based padding to the fragment endpoint
- Add diagonal ignoring to the fragment endpoint
- Add percentile clipping to the fragment endpoint
- Add [0,1]-normalization ignoring to the fragment endpoint

v1.0.4 (2017-07-14)

- Fixed cumulative JSON sizes error
- Fixed fragment loading error (due to py3)

v1.0.3 (2017-07-14)

- Fixed viewconf export (needed to decode slugid.nice())

v1.0.2 (2017-07-13)

- Removed some print statements
- Fixed issues with testing in py3

v1.0.1 (2017-07-13)

- Removed Python 2 support

v1.0.0 (2017-07-13)

- Python 3 support
- API for getting records by name

v0.7.6 (2017-07-08)

- Use cooler transforms
- Always pass NaN values as Float32 arrays

v0.7.5 (2017-07-07)

- Use the binsizes for the individual zoom levels

v0.7.4 (2017-06-20)

- Added ordering to tileset list API

v0.7.3 (2017-06-19)

- Fixed reversion preventing the ingestion of large files

v0.7.2 (2017-06-16)

- Fixed tile data bug

v0.7.1

- Fixed merge conflicts (doh!)

v0.7.0

- Add setting to disable (public) uploads.
- Add settings overloading with `config.json`; see `config.json.sample`.
- Added `higlassVersion` to `viewconf` and extend the endpoint accordingly.
- Code cleanup
- Bug fixes and better error handling

v0.6.2

- Add missing `csv` import

v0.6.1 - 2017-06-06

- Fixed empty tiles bug

v0.6.0

- Removed chromosome table but API remains the same

v0.5.3

- Return coordSystem as part of tileset_info

v0.5.2

- Added test.higlass.io to allowed hosts
- Turned off HashedFilenameStorage

v0.5.1

- Updated requirements to use mirnylab develop cooler

v0.5.0

- Add management command for adding chrom-sizes
- Chrom-sizes endpoint parameter `coords` changes to `id` to avoid confusion. I.e., for one coordinate system there might exist multiple orderings, which means multiple IDs could reference the same coordinate system.

v0.4.4

- Set proper HTTP status codes for errors of the chrom-sizes endpoint
- Robustify internal magic (a.k.a. bug fixes)

v0.4.3

- Fixed an error when the zoom-out levels for fragmentds was negative
- Fixed wrong ordering for multi dataset and/or multi resolution fragment extraction

v0.4.2

- Fixed caching issue in loci extraction

v0.4.1

- Added test server IP to ALLOWED_HOSTS

v0.4.0

- Add endpoints for pulling out fragments aka snippets aka patches of the interaction map
- Add endpoints for chrom-sizes in TSV and JSON format

v0.3.5

- Send min_pos with the tileset info

v0.3.4

- Bug fix for serving unbalanced data

v0.3.3

- Added __str__ to Tileset models so that they're visible in the django
interface

v0.3.2

- Added support for passing SITE_URL as an environment variable

v0.3.0

- Send back float16 data for heatmaps and possibly 1d tracks
