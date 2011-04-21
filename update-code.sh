#!/bin/bash

while true; do
    pushd /home/ubuntu/phantomjs/
    git checkout deploy
    git pull
    qmake && make
    popd
    
    pushd /home/ubuntu/phantom-measurement/
    git checkout deploy
    git pull
    cp /home/ubuntu/phantomjs/bin/phantomjs .    
    source command.sh
    popd
done
