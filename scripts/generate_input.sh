#!/usr/bin/env bash

set -x

PROBLEM_NAME=$1
PROBLEM_SIZE=$2
PROTOCOL=$3
WORKER=$4
NUM_WORKERS=$5

if [[ -z $NUM_WORKERS ]]
then
	echo "Usage:" $0 "problem_name problem_size protocol worker_id num_workers"
	exit 2
fi

pushd ~/work/mage/bin

./example_input $PROBLEM_NAME $PROBLEM_SIZE $NUM_WORKERS

if [[ $PROTOCOL = "ckks" ]]
then
	./ckks_utils keygen
	level=
	if [[ $PROBLEM_NAME = "real_sum" ]]
	then
		level=0
	elif [[ $PROBLEM_NAME = "real_statistics" ]]
	then
		level=2
	else
		level=1
	fi
	./ckks_utils encrypt_file 1 $level ${PROBLEM_NAME}_${PROBLEM_SIZE}_${WORKER}_garbler.input
fi
