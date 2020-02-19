#!/usr/bin/env python

from __future__ import print_function
import argparse, sys
import os

import web_view_mesh.viewer

def main():
    parser = argparse.ArgumentParser(description="Mesh Web Viewer")
    parser.add_argument('--meshdirectory', metavar='MD', help="Mesh Directory",
                        required=True, nargs='?', type=str)
    args = parser.parse_args()
    web_view_mesh.viewer.serve_viewer(args.meshdirectory)

if __name__ == '__main__':
    main()