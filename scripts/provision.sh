#!/usr/bin/env bash

# This script should be run after a hard reboot of the machine. It sets up
# the local disk and creates the cgroup afresh.

DISK_DEVICE=/dev/disk/cloud/azure_resource
CGROUP_NAME=memprog1gb

# These lines below are commented out since I accomplished the same thing
# using cloud-init.
# sudo sfdisk $DISK_DEVICE << EOF
# label: gpt
# ,150GiB,S,
# ,150GiB,S,
# ,+,L,
# EOF
# sudo mkswap ${DISK_DEVICE}2
# sudo swapon ${DISK_DEVICE}2
# sudo mkfs.ext4 ${DISK_DEVICE}3

mkdir -p ~/work
sudo mount ${DISK_DEVICE}-part3 ~/work
sudo chown $(whoami):$(whoami) ~/work
cp -r /opt/* ~/work

mkdir -p ~/logs

sudo cgcreate -g memory:${CGROUP_NAME}
echo 1G | sudo tee /sys/fs/cgroup/memory/${CGROUP_NAME}/memory.limit_in_bytes
