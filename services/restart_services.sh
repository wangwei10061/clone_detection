#! /bin/bash

function restart_service() {
    old_pid=$(ps ax|grep $1.py|grep -v grep|awk '{print $1}')
    echo "old_pid=${old_pid}"
    if [ -z $old_pid ];then
        echo "Process Non-existent!"
        echo "Starting Process...."
        nohup python $1.py > $1.log 2>&1 &
    else
        kill -9 ${old_pid}
        mid_pid=$(ps ax|grep $1.py|grep -v grep|awk '{print $1}')
        if [ -z ${mid_pid} ];then
            echo "Process Close Success!"
            echo "Start Restarting....."
            nohup python $1.py > $1.log 2>&1 &
        else
            echo "Process Close Fail !"
            exit 1
        fi
    fi
    new_pid=$(ps ax|grep $1.py|grep -v grep|awk '{print $1}')
    if [ -z ${new_pid} ];then
        echo "Restart Fail!"
    else
        echo "Restart Success!"
        echo "new_pid=${new_pid}"
}

restart_service CodeStartPerception