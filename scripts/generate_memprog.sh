#!/usr/bin/env bash

set -x

PROBLEM_NAME=$1
PROBLEM_SIZE=$2
PROTOCOL=$3
CONFIG=$4
PARTY=$5
WORKER=$6
LOG_NAME=$7

if [[ -z $WORKER ]]
then
	echo "Usage:" $0 "problem_name problem_size protocol config party_id worker_id [log_file_name]"
	exit 2
fi

pushd ~/work/mage/bin

sudo swapoff -a

if [[ -z $LOG_NAME ]]
then
	./planner $PROBLEM_NAME $PROTOCOL $CONFIG $PARTY $WORKER $PROBLEM_SIZE
else
	# Benchmark this one
	sudo free
	sudo sync
	echo 3 | sudo tee /proc/sys/vm/drop_caches
	sudo free

	/usr/bin/time -v ./planner $PROBLEM_NAME $PROTOCOL $CONFIG $PARTY $WORKER $PROBLEM_SIZE > ~/logs/${LOG_NAME}.planning 2> ~/logs/${LOG_NAME}.planstats
fi

rm -f ${PROBLEM_NAME}_${PROBLEM_SIZE}_${WORKER}.prog ${PROBLEM_NAME}_${PROBLEM_SIZE}_${WORKER}.repprog ${PROBLEM_NAME}_${PROBLEM_SIZE}_${WORKER}.ann
