import numpy as np
import pandas as pd
import cooler
import bbi


TILE_SIZE = 1024


def get_quadtree_depth(chromsizes):
    tile_size_bp = TILE_SIZE
    min_tile_cover = np.ceil(sum(chromsizes) / tile_size_bp)
    return int(np.ceil(np.log2(min_tile_cover)))


def get_zoom_resolutions(chromsizes):
    return [2**x for x in range(get_quadtree_depth(chromsizes) + 1)][::-1]


def get_chromsizes(bwpath):
    """
    TODO: replace this with negspy
    
    Also, return NaNs from any missing chromosomes in bbi.fetch
    
    """
    chromsizes = bbi.chromsizes(bwpath)
    chromosomes = cooler.util.natsorted(chromsizes.keys())
    return pd.Series(chromsizes)[chromosomes]


def abs2genomic(chromsizes, start_pos, end_pos):
    abs_chrom_offsets = np.r_[0, np.cumsum(chromsizes.values)]
    cid_lo, cid_hi = np.searchsorted(abs_chrom_offsets,
                                     [start_pos, end_pos],
                                     side='right') - 1
    rel_pos_lo = start_pos - abs_chrom_offsets[cid_lo]
    rel_pos_hi = end_pos - abs_chrom_offsets[cid_hi]
    start = rel_pos_lo
    for cid in range(cid_lo, cid_hi):
        yield cid, start, chromsizes[cid]
        start = 0
    yield cid_hi, start, rel_pos_hi


def get_bigwig_tile(bwpath, zoom_level, start_pos, end_pos):
    chromsizes = get_chromsizes(bwpath)
    resolutions = get_zoom_resolutions(chromsizes)
    binsize = resolutions[zoom_level]
   
    arrays = []
    for cid, start, end in abs2genomic(chromsizes, start_pos, end_pos):
        n_bins = int(np.ceil((end - start) / binsize))
        try:
            chrom = chromsizes.index[cid]
            clen = chromsizes.values[cid]

            x = bbi.fetch(bwpath, chrom, start, end,
                          bins=n_bins, missing=np.nan)

            # drop the very last bin if it is smaller than the binsize
            if end == clen and clen % binsize != 0:
                x = x[:-1]
        except IndexError:
            # beyond the range of the available chromosomes
            # probably means we've requested a range of absolute
            # coordinates that stretch beyond the end of the genome
            x = np.zeros(n_bins)

        arrays.append(x)

    return np.concatenate(arrays)


def get_bigwig_tile_by_id(bwpath, zoom_level, tile_pos):
    '''
    Get the data for a bigWig tile given a tile id.

    Parameters
    ----------
    bwpath: string
        The path to the bigWig file (can be remote)
    zoom_level: int
        The zoom level to get the data for
    tile_pos: int
        The position of the tile
    '''
    max_depth = get_quadtree_depth(get_chromsizes(bwpath))
    tile_size = TILE_SIZE * 2 ** (max_depth - zoom_level)

    start_pos = tile_pos * tile_size
    end_pos = start_pos + tile_size

    return get_bigwig_tile(bwpath, zoom_level, start_pos, end_pos)

