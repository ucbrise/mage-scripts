#!/usr/bin/env bash

set -x

SCENARIO=$1
LIMIT=$2
PROTOCOL=$3
CONFIG=$4
PARTY=$5
WORKER=$6
PROGRAM=$7
LOG_NAME=$8
CHECK_RESULT=$9

if [[ -z $CHECK_RESULT ]]
then
	echo "Usage:" $0 "scenario limit protocol config party_id worker_id program_name log_file_name check_result[true/false]"
	exit
fi

pushd ~/work/mage/bin

PREFIX=
if [[ $SCENARIO = "mage" ]]
then
	sudo swapoff -a
	PREFIX="sudo cgexec -g memory:memprog${LIMIT}"
elif [[ $SCENARIO = "unbounded" ]]
then
	sudo swapoff -a
	PREFIX="sudo"
elif [[ $SCENARIO = "os" ]]
then
	sudo swapoff -a
	sudo swapon /dev/disk/cloud/azure_resource-part2
	PREFIX="sudo cgexec -g memory:memprog${LIMIT}"
else
	echo "Unknown scenario" $SCENARIO
	exit 2
fi

sudo free
sudo sync
echo 3 | sudo tee /proc/sys/vm/drop_caches
sudo free

$PREFIX ./mage $PROTOCOL $CONFIG $PARTY $WORKER $PROGRAM > ~/logs/${LOG_NAME}.log

if [[ $CHECK_RESULT = true ]]
then
	if [[ $PROTOCOL = "halfgates" ]]
	then
		# Only garbler can print this out
		if [[ $PARTY = 1 ]]
		then
			diff ${PROGRAM}_${WORKER}.output ${PROGRAM}_${WORKER}.expected > ~/logs/${LOG_NAME}.result
		fi
	elif [[ $PROTOCOL = "ckks" ]]
	then
		./ckks_utils decrypt_file 1 ${PROGRAM}_${WORKER}.output
		./ckks_utils float_file_decode ${PROGRAM}_${WORKER}.output > decoded.output
		./ckks_utils float_file_decode ${PROGRAM}_${WORKER}.expected > expected.output
		diff decoded.output expected.output > ~/logs/${LOG_NAME}.result
		rm ${PROGRAM}_${WORKER}_garbler.input
	else
		echo "Unknown protocol" $PROTOCOL
	fi
fi
