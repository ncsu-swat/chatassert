#!/bin/bash

THISDIR=$(dirname `find $(pwd) -name $0`)
ROOTDIR="$THISDIR/../../"
export PYTHONPATH="$ROOTDIR/src"
(cd $ROOTDIR;
 # make sure virtual environment is available
 bash create_venv.sh
 source env/bin/activate
 (cd src/main;
  python doall.py
 )
)


