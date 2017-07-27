# Public API

## `/api/v1/fragments_by_loci/`

**Type**: `POST`

**Body**: `JSON`

The body needs to contain a [BEDPE](https://bedtools.readthedocs.io/en/latest/content/general-usage.html#bedpe-format)-like array with the loci determening the fragments to be retrieved. Each locus is represented as an array of the following form:

```javascript
[ chrom1, start1, end1, chrom2, start2, end2, dataUuid, zoomOutLevel ]
```

The columns need to be of the following form:

- chrom1 _(str)_:

  First chromosome. E.g., `chr1` or `1`.

- start1 _(int)_:

  First start position in base pairs relative to `chrom1`. E.g., `0` or `1`.

- end1 _(int)_:

  First end position in base pairs relative to `chrom1`. E.g., `chr1` or `1`.

- chrom2 _(str)_:

  Second chromosome. E.g., `chr1` or `1`.

- start2 _(int)_:

  Second start position in base pairs relative to `chrom2`. E.g., `0` or `1`.

- end2 _(int)_:

  Second end position in base pairs relative to `chrom2`. E.g., `chr1` or `1`.

- dataUuid _(str)_:

  UUID of HiGlass server of the tileset representing a Hi-C map. E.g., `OHJakQICQD6gTD7skx4EWA`.

- zoomOutLevel _(int)_:

  Inverted zoom level at which the fragment should be cut out. E.g., For GM12878 of Rao et al. (2014) at 1KB resolution, a _zoom out level_ of `0` corresponds to `1KB`, `1` corresponds to `2KB`, `2` corresponds to `4KB`, etc.


For example:

```javascript
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

- dims _(int)_:

  Width and height of the fragment in pixels. Defaults to `22`.

- padding _(int)_:

  Percental padding related to the dimension of the fragment. E.g., 10 = 10% padding (5% per side). Defaults to `10`.

- percentile _(float)_:

  Percentile clip. E.g., For 99 the maximum will be capped at the 99-percentile. Defaults to `100.0`.

- no-balance _(bool)_:

  If `True` the fragment will **not** be balanced using Cooler. Defaults to `False`.

- no-normalize _(bool)_:

  If `True` the fragment will **not** be normalized to [0, 1]. Defaults to `False`.

- ignore-diags _(int)_:

  Number of diagonals to be ignored, i.e., set to 0. Defaults to `0`.

- no-cache _(bool)_:

  If `True` the fragment will not be retrieved from cache. This is useful for development. Defaults to `False`.

- precision _(int)_:

  Determines the float precision of the returned fragment. Defaults to `2`.

**Return** _(obj)_:

```
{
  "fragments": [
    [
      [0, 0.48, 0, 0.04],
      [0.48, 0, 1, 0.07],
      [0, 1, 0, 0.47],
      [0.04, 0.07, 0.47, 0]
    ],
    ...
  ]
}
```

_(This example comes from a request of `/api/v1/fragments_by_loci/?precision=2&dims=4&ignore-diags=1&percentile=99`)_
