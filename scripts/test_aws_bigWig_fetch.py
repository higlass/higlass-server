import sys
import argparse
import tilesets.bigwig_tiles as bwt

def main():
    parser = argparse.ArgumentParser(description="""
    
    python test_bigwig_tile_fetch.py filename zoom_level tile_pos
""")

    parser.add_argument('filename')
    parser.add_argument('zoom_level')
    parser.add_argument('tile_pos')
    #parser.add_argument('argument', nargs=1)
    #parser.add_argument('-o', '--options', default='yo',
    #					 help="Some option", type='str')
    #parser.add_argument('-u', '--useless', action='store_true', 
    #					 help='Another useless option')

    args = parser.parse_args()

    print("tile", bwt.get_bigwig_tile_by_id(args.filename, 
        int(args.zoom_level),
        int(args.tile_pos)))

if __name__ == "__main__":
    main()
