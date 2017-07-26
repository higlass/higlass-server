# Public API

**Global prefix**: `/api/v1/`

## /fragments_by_loci/

**Type**: `POST`

**Body**: `JSON`

The body needs to contain a [BEDPE](https://bedtools.readthedocs.io/en/latest/content/general-usage.html#bedpe-format)-like array with the loci determening the fragments to be retrieved. Each locus is represented as an array of the following form:

```
[ chrom1, start1, end1, chrom2, start2, end2, dataUuid, zoomOutLevel ]
```

The columns need to be of the following form:

- chrom1 (str):

  First chromosome. E.g., `chr1` or `1`.

- start1 (int):

  First start position in base pairs relative to `chrom1`. E.g., `0` or `1`.

- end1 (int):

  First end position in base pairs relative to `chrom1`. E.g., `chr1` or `1`.

- chrom2 (str):

  Second chromosome. E.g., `chr1` or `1`.

- start2 (int):

  Second start position in base pairs relative to `chrom2`. E.g., `0` or `1`.

- end2 (int):

  Second end position in base pairs relative to `chrom2`. E.g., `chr1` or `1`.

- dataUuid (str):

  UUID of HiGlass server of the tileset representing a Hi-C map. E.g., `OHJakQICQD6gTD7skx4EWA`.

- zoomOutLevel (int):

  Inverted zoom level at which the fragment should be cut out. E.g., For GM12878 of Rao et al. (2014) at 1KB resolution, a _zoom out level_ of `0` corresponds to `1KB`, `1` corresponds to `2KB`, `2` corresponds to `4KB`, etc.


For example:

```JSON
[
  [
    "chr1",
    0,
    500000000,
    "chr1",
    0,
    500000000,
    "uuid-of-my-fancy-hi-c-map",
    0
  ]
]
```

**Parameters**:

- dims (int)

  Width and height of the fragment in pixels. Defaults to `22`.

- padding (int)

  Percental padding related to the dimension of the fragment. E.g., 10 = 10% padding (5% per side). Defaults to `10`.

- percentile (float)

  Percentile clip. E.g., For 99 the maximum will be capped at the 99-percentile. Defaults to `100.0`.

- no-balance (bool)

  If `True` the fragment will **not** be balanced using Cooler. Defaults to `False`.

- no-normalize (bool)

  If `True` the fragment will **not** be normalized to [0, 1]. Defaults to `False`.

- ignore-diags (int)

  Number of diagonals to be ignored, i.e., set to 0. Defaults to `0`.

- no-cache (bool)

  If `True` the fragment will not be retrieved from cache. This is useful for development. Defaults to `False`.

- precision (int)

  Determines the float precision of the returned fragment. Defaults to `2`.
