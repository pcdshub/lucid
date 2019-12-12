#!/bin/bash

CWD=`pwd`
CONFIG=${CWD}/happi_demo.cfg
TOOLBAR=${CWD}/demo_toolbar.yml
BEAMLINE=DEMO_BEAMLINE

HAPPI_CFG=${CONFIG} lucid --toolbar=${TOOLBAR} ${BEAMLINE}
