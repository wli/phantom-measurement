#! /bin/bash

if [ "$1" = "start" ]; then
/home/ubuntu/update-code.sh > /home/ubuntu/phantom-measurement.log &
exit
fi

if [ "$1" = "stop" ]; then
exit
fi
