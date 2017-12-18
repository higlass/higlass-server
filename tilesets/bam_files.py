import random
import numpy as np

def sample_reads(samfile, num_entries=256, entry_length=10000, 
        start_pos=None, 
        end_pos=None,
        chrom_order=None):
    '''
    Sample reads from the specified region, assuming that the chromosomes
    are ordered in some fashion. Returns an list of pysam reads

    Parameters:
    -----------
    samfile: pysam.AlignmentFile
        A pysam entry into an indexed bam file
    num_entries: int
        The number of reads to sample
    entry_length: int
        The number of base pairs to sample in this file
    start_pos: int
        The start position of the sampled region
    end_pos: int
        The end position of the sampled region
    chrom_order: ['chr1', 'chr2',...]
        A listing of chromosome names to use as the order

    Returns
    -------
    reads: [read1, read2...]
        The list of in the sampled regions
    '''

    total_length = sum(samfile.lengths)
    #print("tl:", total_length, np.cumsum(np.array(samfile.lengths)))
    
    if start_pos is None:
        start_pos = 1
    if end_pos is None:
        end_pos = total_length
    
    # limit the total length by the number of bases that we're going
    # to fetch
    poss = [int(i) for i in 
            np.linspace(start_pos, end_pos - entry_length, num_entries)]

    # if chromorder is not None...
    # specify the chromosome order for the fetched reads
    
    lengths = []
    for pos in poss:
        #print("pos:", pos)
        seq_num = np.flatnonzero(np.cumsum(np.array(samfile.lengths)) >= pos)[0]
        seq_name = samfile.references[seq_num]
        cname = '{}'.format(seq_name)
        
        pos = random.randint(0,1000000)

        
        i = samfile.fetch(cname, pos, pos + entry_length)

        a = list(i)
        lengths += [len(a)]
        
        #samfile.count_coverage(cname, pos, pos + entry_length)
        
    return lengths
