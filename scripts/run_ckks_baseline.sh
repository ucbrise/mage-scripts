#!/usr/bin/env bash

set -x

SCENARIO=$1
PROBLEM_SIZE=$2
LOG_NAME=$3

if [[ -z $LOG_NAME ]]
then
	echo "Usage:" $0 "scenario problem_size log_file_name"
	exit
fi

PROBLEM_NAME=real_statistics
PROGRAM=${PROBLEM_NAME}_${PROBLEM_SIZE}
WORKER=0

pushd ~/work/mage/bin

PREFIX=
if [[ $SCENARIO = "unbounded" ]]
then
	sudo swapoff -a
	PREFIX="sudo"
elif [[ $SCENARIO = "os" ]]
then
	sudo swapoff -a
	sudo swapon /dev/disk/cloud/azure_resource-part2
	PREFIX="sudo cgexec -g memory:memprog1gb"
else
	echo "Unknown/unsupported scenario" $SCENARIO
	exit 2
fi

sudo free
sudo sync
echo 3 | sudo tee /proc/sys/vm/drop_caches
sudo free

$PREFIX ./ckks_utils $PROBLEM_NAME $PROBLEM_SIZE ${PROGRAM}_${WORKER}_garbler.input ${PROGRAM}_${WORKER}.output > ~/logs/${LOG_NAME}.log

if [[ $CHECK_RESULT = true ]]
then
	./ckks_utils decrypt_file 1 ${PROGRAM}_${WORKER}.output
	./ckks_utils float_file_decode ${PROGRAM}_${WORKER}.output > decoded.output
	./ckks_utils float_file_decode ${PROGRAM}_${WORKER}.expected > expected.output
	diff decoded.output expected.output > ~/logs/${LOG_NAME}.result
fi
