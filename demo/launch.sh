#!/bin/bash

CWD=`pwd`
CONFIG=${CWD}/happi_demo.cfg
TOOLBAR=${CWD}/example_toolbar.yml
BEAMLINE=DEMO_BEAMLINE

if [ "$LUCID_DEBUG" == "1" ]; then
    HAPPI_CFG=${CONFIG} ipython -i `which lucid` -- --toolbar=${TOOLBAR} ${BEAMLINE}
else
    HAPPI_CFG=${CONFIG} lucid --toolbar=${TOOLBAR} ${BEAMLINE}
fi
