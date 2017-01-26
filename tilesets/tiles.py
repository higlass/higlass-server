import cooler.contrib.higlass as cch
import logging
import numpy as np

logger = logging.getLogger(__name__)


def make_tile(zoomLevel, x_pos, y_pos, dset):
    info = dset[1]
    divisor = 2 ** zoomLevel

    start1 = x_pos * info['max_width'] / divisor
    end1 = (x_pos + 1) * info['max_width'] / divisor
    start2 = y_pos * info['max_width'] / divisor
    end2 = (y_pos + 1) * info['max_width'] / divisor

    data = cch.get_data(
        dset[0], zoomLevel, start1, end1 - 1, start2, end2 - 1
    )

    df = data[data['genome_start'] >= start1]
    binsize = dset[0].attrs[str(zoomLevel)]
    j = (df['genome_start'].values - start1) // binsize
    i = (df['genome_end'].values - start2) // binsize
    v = np.nan_to_num(df['balanced'].values)

    zi = zip(zip(i, j), v)
    tile_bins = dict(zi)
    denseOutputArray = []
    for i in range(0, 256):
        for j in range(0, 256):
            if (i, j) in tile_bins:
                denseOutputArray.append(tile_bins[(i, j)])
            else:
                denseOutputArray.append(0)

    return np.array(denseOutputArray, dtype=np.float32)
