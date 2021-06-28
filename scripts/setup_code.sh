#!/usr/bin/env bash

cd ~/work

if [[ $1 != "mage" ]]
then
    # Clone MAGE (will build it later)
    git clone https://github.com/ucbrise/mage

    # Clone and build EMP-toolkit baseline
    git clone https://github.com/emp-toolkit/emp-tool
    pushd emp-tool
    git checkout 8f95ba4f79bc15d4646e9137f2018b1a12a1343a
    cmake .
    sudo make install
    popd

    git clone https://github.com/emp-toolkit/emp-ot
    pushd emp-ot
    git checkout 0f4a1e41a25cf1a034b5796752fde903a241f482
    cmake .
    sudo make install
    popd

    git clone https://github.com/samkumar/emp-sh2pc
    pushd emp-sh2pc
    git checkout adef68a1631b4ab9f2027088ed1deee7e94024e9
    cmake .
    sudo make install
    popd
fi

# Use the version of MAGE specified on the command line
REMOTE=tobuild
pushd mage
git remote add $REMOTE $2
git fetch $REMOTE
git checkout ${REMOTE}/${3}
make
popd
