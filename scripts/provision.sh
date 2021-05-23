#!/usr/bin/env bash

# This script should be run after a hard reboot of the machine. It sets up
# the local disk and creates the cgroup afresh.

if [[ $1 = "azure" ]]
then
    if [[ -e /dev/disk/azure/scsi1/lun0 ]]
    then
        DISK_DEVICE=/dev/disk/azure/scsi1/lun0
        sudo mkfs.ext4 -q $DISK_DEVICE
    elif [[ $2 = "paired-noswap" || $2 = "paired-swap" ]]
    then
        DISK_DEVICE=/dev/disk/cloud/azure_resource-part1
        if [[ $2 = "paired-swap" ]]
        then
            ln -s /dev/disk/cloud/azure_resource-part2 swap_device
        fi
    else
        DISK_DEVICE=/dev/disk/cloud/azure_resource-part3
        ln -s /dev/disk/cloud/azure_resource-part2 swap_device
    fi
elif [[ $1 = "gcloud" ]]
then
    if [[ $2 = "paired-noswap" || $2 = "paired-swap" ]]
    then
        DISK_DEVICE=/dev/nvme0n1p1
        if [[ $2 = "paired-swap" ]]
        then
            ln -s /dev/nvme0n2p1 swap_device
        fi
    else
        DISK_DEVICE=/dev/nvme0n1p3
        ln -s /dev/nvme0n1p2 swap_device
    fi
else
    echo "Unknown provider" $1
    exit 1
fi

# $DISK_DEVICE is appropriately partitioned using cloud-init, so the lines
# below aren't necessary anymore.

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
sudo mount ${DISK_DEVICE} ~/work
sudo chown $(whoami):$(whoami) ~/work
cp -r /opt/* ~/work

mkdir -p ~/work/scratch
if [[ $1 = "gcloud" && $2 = "paired-noswap" ]]
then
    sudo mount /dev/nvme0n2p1 ~/work/scratch
    sudo chown $(whoami):$(whoami) ~/work/scratch
fi

# Use the latest version of MAGE
REMOTE=tobuild

pushd ~/work/mage
git remote add $REMOTE $3
git fetch $REMOTE
git checkout ${REMOTE}/${4}
make
popd

mkdir -p ~/logs

for memsize in 1g 2g 4g 8g 16g 32g 62g
do
    cgroup_name=memprog${memsize}b
    sudo cgcreate -g memory:${cgroup_name}
    echo $memsize | sudo tee /sys/fs/cgroup/memory/${cgroup_name}/memory.limit_in_bytes
done
