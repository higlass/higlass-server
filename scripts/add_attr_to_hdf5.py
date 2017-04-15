#!/usr/bin/python

import h5py
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="""
    
    python add_attr_to_hdf5.py file.hdf5 attr_name attr_value

    Add an attribute to an HDF5 file.
""")

    parser.add_argument('filepath')
    parser.add_argument('attr_name')
    parser.add_argument('attr_value')
    #parser.add_argument('-o', '--options', default='yo',
    #					 help="Some option", type='str')
    #parser.add_argument('-u', '--useless', action='store_true', 
    #					 help='Another useless option')

    args = parser.parse_args()

    with h5py.File(args.filepath) as f:
        f.attrs[args.attr_name] = args.attr_value
    

if __name__ == '__main__':
    main()


