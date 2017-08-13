# Public API

## `/api/v1/annotation/`

### `GET`

**Parameters**:

- uuid _(string)_:

  UUID of the annotation.

- slug _(string)_:

  Slug of the annotation.

**Return**:

```javascript
{
  "description": "This is such a cool pattern!",
  "patterns": [
    {
      "chrom1": "chr1",
      "start1": 0,
      "end1": 50000000,
      "chrom2": "chr2",
      "start2": 0,
      "end2": 50000000,
      "coords": "hg19",
      "tileset": "CQMd6V_cRw6iCI_-Unl3PQ",
      "zoomOutLevel": 1
    }
  ],
  "slug": "cool-pattern",
  "uuid": "MMMd6V_cRw6iCI_-Unl3PQ"
}
```

### `POST`

**Body** _(JSON)_:

The body needs to be a valid JSON object. It needs to have the `description` and `loci` field, while `slug` is optional

- description _(string)_:

  Textual description of the annotation.

- loci _(array)_:

  List of locations including the tileset UUID and zoom-out level. A location is represented as a JS object of the following form:

  ```javascript
  {
    "chrom1": "chr1",
    "start1": 0,
    "end1": 50000000,
    "chrom2": "chr2",
    "start2": 0,
    "end2": 50000000,
    "coords": "hg19",
    "tileset": "CQMd6V_cRw6iCI_-Unl3PQ",
    "zoomOutLevel": 1
  }
  ```

  _Note: if you want to add a 1D annotation you do not have to specify `chrom2`, `start2`, and `end2`._

- slug _(string)_:

  Slug for the annotation. A slug is a **unique** URL encodable string that identifies the annotation. it is like a UUID but can be freely chosen by the user provide a means of a more human-readible UUID.

**Return**:

When the annotation was successfully saved you will see such a return value:

```javascript
{ "uuid": "N1c3--_cRw6iCI_-Unl3PQ" }
```

otherwise:

```javascript
{ "error": "Some error message" }
```

---

## `/api/v1/annotation-set/`

### `GET`

**Parameters**:

- uuid _(string)_:

  UUID of the annotation. Either `uuid` or `slug` needs to be specified but not both.

- slug _(string)_:

  Slug of the annotation. Either `uuid` or `slug` needs to be specified but not both.

- fetch-patterns _(boolean [optional])_:

  If `true`, i.e., `1`, the return will include the complete information of the annotations. Otherwise, only the annotation UUIDs are returned.

**Return**:

If `fetch-annotations` is **not** passed:

```javascript
{
  "annotations": [
    {
      "description": "This is an awesome pattern over here.",
      "patterns": ["gR34T_1_aNN0_Unl3PQ_q1"],
      "slug": "first-great-annotation",
      "uuid": "gR34T_1_cRw6iCI_Unl3PQ",
    },
    {
      "description": "WOW! Look at this beautiful noise.",
      "patterns": ["gR34T_2_aNN0_Unl3PQ_q1"],
      "slug": "second-great-annotation",
      "uuid": "gR34T_2_cRw6iCI_Unl3PQ",
    }
  ],
  "description": "A collection of the greatest annotations showing the greatness of this great piece of DNA.",
  "slug": "greatest-annotations",
  "uuid": "gR34T__cRw6iCI_-Unl3PQ",
}

otherwise:

```javascript
{
  "annotations": [
    {
      "description": "This is an awesome pattern over here.",
      "patterns": [
        {
          "uuid": "gR34T_1_aNN0_Unl3PQ_q1",
          "chrom1": "chr1",
          "start1": 0,
          "end1": 50000000,
          "chrom2": "chr2",
          "start2": 0,
          "end2": 50000000,
          "coords": "hg19",
          "tileset": "CQMd6V_cRw6iCI_-Unl3PQ",
          "zoomOutLevel": 1,
        }
      ],
      "slug": "first-great-annotation",
      "uuid": "gR34T_1_cRw6iCI_Unl3PQ",
    },
    {
      "description": "WOW! Look at this beautiful noise.",
      "patterns": [
        {
          "uuid": "gR34T_2_aNN0_Unl3PQ_q1",
          "chrom1": "chr1",
          "start1": 0,
          "end1": 50000000,
          "chrom2": "chr3",
          "start2": 0,
          "end2": 50000000,
          "coords": "hg19",
          "tileset": "CQMd6V_cRw6iCI_-Unl3PQ",
          "zoomOutLevel": 1,
        }
      ],
      "slug": "second-great-annotation",
      "uuid": "gR34T_2_cRw6iCI_Unl3PQ",
    }
  ],
  "description": "A collection of the greatest annotations showing the greatness of this great piece of DNA.",
  "slug": "greatest-annotations",
  "uuid": "gR34T__cRw6iCI_-Unl3PQ",
}
```

### `POST`

**Body** _(JSON)_:

The body needs to be a valid JSON object. It needs to have the `description` and `loci` field, while `slug` is optional

- description _(string)_:

  Textual description of the annotation.

- loci _(array)_:

  List of locations including the tileset UUID and zoom-out level. A location is represented as a JS object of the following form:

  ```javascript
  {
    "chrom1": "chr1",
    "start1": 0,
    "end1": 50000000,
    "chrom2": "chr2",
    "start2": 0,
    "end2": 50000000,
    "coords": "hg19",
    "tileset": "CQMd6V_cRw6iCI_-Unl3PQ",
    "zoomOutLevel": 1
  }
  ```

  _Note: if you want to add a 1D annotation you do not have to specify `chrom2`, `start2`, and `end2`._

- slug _(string)_:

  Slug for the annotation. A slug is a **unique** URL encodable string that identifies the annotation. it is like a UUID but can be freely chosen by the user provide a means of a more human-readible UUID.

**Return**:

When the annotation was successfully saved you will see such a return value:

```javascript
{ "uuid": "N1c3--_cRw6iCI_-Unl3PQ" }
```

otherwise:

```javascript
{ "error": "Some error message" }
```


---

## `/api/v1/fragments_by_loci/`

### `POST`

**Body** _(JSON)_:

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

```javascript
{
  "fragments": [
    [
      [0, 0.48, 0, 0.04],
      [0.48, 0, 1, 0.07],
      [0, 1, 0, 0.47],
      [0.04, 0.07, 0.47, 0]
    ]
  ]
}
```

_(This example comes from a request of `/api/v1/fragments_by_loci/?precision=2&dims=4&ignore-diags=1&percentile=99`)_

---

## `/api/v1/chrom-sizes/`

### `GET`

**Parameters**:

- id _(string)_:

  The UUID of the chrom-sizes.

- type _(string)_:

  Return type. Currently supports `tsv` and `json`.

- cum _(boolean)_:

  If `type` is `json`, one can additionally return the cumulative size by setting this to a truthy value like `1`.

**Return**:

A TSV response looks like this:
```
chr1    3
chr2    2
chr2    1
...
```

A JSON response looks like this:
```javascript
{
    chr1: {
        size: 3,
        offset: 0
    },
    chr2: {
        size: 2,
        offset: 3
    },
    chr2: {
        size: 1,
        offset: 5
    },
    ...
}
```
