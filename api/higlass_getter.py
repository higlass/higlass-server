from __future__ import division, print_function
import json

import numpy as np
import pandas as pd
import cooler
import h5py
import time

TILESIZE = 256

where = np.flatnonzero
chromsizes = cooler.read_chromsizes('http://s3.amazonaws.com/pkerp/data/hg19/chromInfo.txt')  # defaults to reading chr#,X,Y,M
chromosomes = list(chromsizes.keys())
chromid_map = dict(zip(chromosomes, range(len(chromosomes))))
cumul_lengths = np.r_[0, np.cumsum(chromsizes)]

def absCoord2bin(c, pos):
    try:
        cid = where(cumul_lengths > pos)[0] - 1
    except IndexError:
        return c.info['nbins']
    chrom = chromosomes[cid]
    relPos = pos - cumul_lengths[cid]
    return  c.offset( (chrom, relPos, chromsizes[chrom]) )


def getData(FILEPATH, zoomLevel, startPos1, endPos1, startPos2, endPos2):

    groupname = str(zoomLevel)

    with h5py.File(FILEPATH, 'r') as f:
        c = cooler.Cooler(f[groupname])

        i0 = absCoord2bin(c, startPos1)
        i1 = absCoord2bin(c, endPos1)
        j0 = absCoord2bin(c, startPos2)
        j1 = absCoord2bin(c, endPos2)
        mat = c.matrix(balance=True)[i0:i1, j0:j1]

    flat = list(mat.toarray().ravel())

    return json.dumps({'dense': flat})

def getData3(fpath, zoomLevel, startPos1, endPos1, startPos2, endPos2):
    t1 = time.time()
    f = h5py.File(fpath,'r')
    c = cooler.Cooler(f[str(zoomLevel)])
    matrix = c.matrix(balance=True, as_pixels=True, join=True)
    cooler_matrix = {'cooler': c, 'matrix': matrix}
    c = cooler_matrix['cooler']

    i0 = absCoord2bin(c, startPos1)
    i1 = absCoord2bin(c, endPos1)
    j0 = absCoord2bin(c, startPos2)
    j1 = absCoord2bin(c, endPos2)


    if (i1-i0) == 0 or (j1-j0) == 0:
        return pd.DataFrame(columns=['genome_start', 'genome_end', 'balanced'])

    pixels = c.matrix(as_pixels=True, max_chunk=np.inf)[i0:i1, j0:j1]

    if not len(pixels):
        return pd.DataFrame(columns=['genome_start', 'genome_end', 'balanced'])

    lo = min(i0, j0)
    hi = max(i1, j1)
    bins = c.bins()[['chrom', 'start', 'end', 'weight']][lo:hi]
    bins['chrom'] = bins['chrom'].cat.codes
    pixels = cooler.annotate(pixels, bins)
    pixels['genome_start'] = cumul_lengths[pixels['chrom1']] + pixels['start1']
    pixels['genome_end']   = cumul_lengths[pixels['chrom2']] + pixels['end2']
    pixels['balanced']     = pixels['count'] * pixels['weight1'] * pixels['weight2']
    #print  type(pixels[map(lambda x: "{0:.2f}".format(x),map(lambda x: float(x),['genome_start', 'genome_end', 'balanced']))])

    return pixels[['genome_start', 'genome_end', 'balanced']]
	
    #return pixels[map(lambda x: "{0:.2f}".format(x),map(lambda x: float(x),['genome_start', 'genome_end', 'balanced']))]


def getInfo(FILEPATH):

    with h5py.File(FILEPATH, 'r') as f:
        total_length = int(cumul_lengths[-1])
        binsize = int(f['0'].attrs['bin-size'])
        binsize = 1000
        n_tiles = total_length / binsize / TILESIZE
        print("total_length:", total_length, binsize, TILESIZE)
        n_zooms = int(np.ceil(np.log2(n_tiles)))
        max_width = binsize * TILESIZE * 2**n_zooms

        info = {
            'min_pos': [0.0, 0.0],
            'max_pos': [total_length, total_length],
            'max_zoom': n_zooms,
            'max_width': max_width,
            'bins_per_dimension': TILESIZE,
        }

    return info

    return json.dumps(info)
