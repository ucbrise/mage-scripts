#!/usr/bin/env bash

set -x

PROBLEM_NAME=$1
PROBLEM_SIZE=$2
PROTOCOL=$3
CONFIG=$4
PARTY=$5
WORKER=$6
LOG_NAME=$7

if [[ -z $LOG_NAME ]]
then
	echo "Usage:" $0 "problem_name problem_size protocol config party_id worker_id log_file_name"
	exit 2
fi

pushd ~/work/mage/bin

./planner $PROBLEM_NAME $PROTOCOL $CONFIG $PARTY $WORKER $PROBLEM_SIZE > ~/logs/$LOG_NAME.planning
rm -f *.prog *.repprog *.ann
