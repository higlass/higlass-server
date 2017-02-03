#!/usr/bin/python

from __future__ import print_function

import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="""
    
    python format_upload_command.py formatted_filename

    Create higlass server curl command to upload the file with this filename.

    Example filename:

    Dixon2012-IMR90-HindIII-allreps-filtered.1kb.multires.cool

    Example output:

    ...
""")

    parser.add_argument('filename')
    #parser.add_argument('argument', nargs=1)
    #parser.add_argument('-o', '--options', default='yo',
    #					 help="Some option", type='str')
    #parser.add_argument('-u', '--useless', action='store_true', 
    #					 help='Another useless option')

    args = parser.parse_args()

    parts = args.filename.split('-')

    try:
        name = parts[0][:-4]
        year = parts[0][-4:]
        celltype = parts[1]
        enzyme = parts[2]
        resolution = parts[4].split('.')[1]

        out_txt = """
    curl -u `cat ~/.higlass-server-login` \
     -F 'datafile=@/data/downloads/hg19/{filename}' \
     -F 'filetype=cooler' \
     -F 'datatype=matrix' \
     -F 'name={name} et al. ({year}) {celltype} {enzyme} (allreps) {resolution}' \
     -F 'coordSystem=hg19' \
     localhost:8000/api/v1/tilesets/""".format(filename=args.filename, name=name, year=year, celltype=celltype, enzyme=enzyme, resolution=resolution)

        print(out_txt, end="")
    except:
        print("ERROR:", args.filename)
    

if __name__ == '__main__':
    main()


