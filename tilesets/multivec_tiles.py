import numpy as np

def abs2genomic(chromsizes, start_pos, end_pos):
    '''
    Convert absolute genomic sizes to genomic
    
    Parameters:
    -----------
    chromsizes: [1000,...]
        An array of the lengths of the chromosomes
    start_pos: int
        The starting genomic position
    end_pos: int
        The ending genomic position
    '''
    abs_chrom_offsets = np.r_[0, np.cumsum(chromsizes)]
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

def get_tile(f, chromsizes, resolution, start_pos, end_pos, shape):
    '''
    Get the tile value given the start and end positions and
    chromosome positions. 
    
    Drop bins at the ends of chromosomes if those bins aren't
    full.
    
    Parameters:
    -----------
    f: h5py.File
        An hdf5 file containing the data
    chromsizes: [('chr1', 1000), ....]
        An array listing the chromosome sizes
    resolution: int
        The size of each bin, except for the last bin in each
        chromosome.
    start_pos: int
        The start_position of the interval to return
    end_pos: int
        The end position of the interval to return
        
    Returns
    -------
    return_vals: [...]
        A subset of the original genome-wide values containing
        the values for the portion of the genome that is visible.
    '''
    binsize = resolution
    print('start_pos:', start_pos, 'end_pos:', end_pos)
    print('shape:', shape)

    arrays = []
    for cid, start, end in abs2genomic([c[1] for c in chromsizes], start_pos, end_pos):
        n_bins = int(np.ceil((end - start) / binsize))
        print("cid:", cid, 'n_bins:', n_bins)
        
        try:
            chrom = chromsizes[cid][0]
            clen = chromsizes[cid][1]

            print('chrom:', chrom)

            start_pos = start // binsize
            end_pos = end // binsize

            print('start:', start, 'end:', end)
            print('binsize:', binsize, 'resolution:', resolution)
            
            x = f['resolutions'][str(resolution)]['values'][chrom][start_pos:end_pos]
            print("x:", x.shape)

            # drop the very last bin if it is smaller than the binsize
            if len(x) > 1 and end == clen and clen % binsize != 0:
                print("dropping")
                x = x[:-1]
        except IndexError:
            # beyond the range of the available chromosomes
            # probably means we've requested a range of absolute
            # coordinates that stretch beyond the end of the genome
            print('zeroes')
            x = np.zeros((n_bins, shape[1]))

        arrays.append(x)

    return np.concatenate(arrays)
