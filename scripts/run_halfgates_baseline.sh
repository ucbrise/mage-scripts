#!/usr/bin/env bash

set -x

SCENARIO=$1
PARTY=$2
PROBLEM_SIZE=$3
OTHER_IP=$4
LOG_NAME=$5

if [[ -z $LOG_NAME ]]
then
	echo "Usage:" $0 "scenario party_id log_file_name"
	exit 2
fi

pushd ~/work/emp-sh2pc/bin

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

$PREFIX ./merge_sorted $PARTY 50000 $PROBLEM_SIZE $OTHER_IP > ~/logs/${LOG_NAME}.log
