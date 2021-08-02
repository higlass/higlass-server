import sys
import math
import argparse
import clodius.tiles.bigwig as hgbi
import clodius.tiles.utils as hgut
import time

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
    chromsizes = hgbi.get_chromsizes(bwpath)
    max_depth = hgut.get_quadtree_depth(chromsizes, hgbi.TILE_SIZE)
    tile_size = hgbi.TILE_SIZE * 2 ** (max_depth - zoom_level)

    start_pos = tile_pos * tile_size
    end_pos = start_pos + tile_size

    return hgbi.get_bigwig_tile(bwpath, zoom_level, start_pos, end_pos)

def main():
    parser = argparse.ArgumentParser(description="""
    
    python test_bigwig_tile_fetch.py filename zoom_level tile_pos
""")

    parser.add_argument('filename')
    parser.add_argument('zoom_level')
    parser.add_argument('tile_pos')
    parser.add_argument('--num-requests', default=1, type=int)
    #parser.add_argument('argument', nargs=1)
    #parser.add_argument('-o', '--options', default='yo',
    #					 help="Some option", type='str')
    #parser.add_argument('-u', '--useless', action='store_true', 
    #					 help='Another useless option')
    args = parser.parse_args()

    print("fetching:", args.filename)
    if args.num_requests == 1:
        tile = get_bigwig_tile_by_id(args.filename, int(args.zoom_level),
            int(args.tile_pos))
    else:
        zoom_level = math.ceil(math.log(args.num_requests) / math.log(2))

        for tn in range(0, args.num_requests):
            print("fetching:", zoom_level, tn)
            t1 = time.time()
            tile = get_bigwig_tile_by_id(args.filename, int(zoom_level),
                int(tn))
            t2 = time.time()
            print("fetched: {:.2f}".format(t2 - t1), "tile", len(tile))


if __name__ == "__main__":
    main()
