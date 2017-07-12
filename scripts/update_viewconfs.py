#!/usr/bin/python

import json
import requests
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="""
    
    python change_chromosome_axis_viewconfs.py server
""")

    parser.add_argument('server')
    #parser.add_argument('-o', '--options', default='yo',
    #					 help="Some option", type='str')
    #parser.add_argument('-u', '--useless', action='store_true', 
    #					 help='Another useless option')

    args = parser.parse_args()

    r = requests.get(args.server + "/viewconfs/")

    if r.status_code != 200:
        print("Bad return:", r.status_code, r.content)
        return

    content = json.loads(r.content)
    

if __name__ == '__main__':
    main()


