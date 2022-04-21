#!/bin/bash

restart_service()
{
    service_name=$1
    script_name="$service_name.py"
    log_name="$service_name.log"
    old_pid=$(ps ax|grep $script_name|grep -v grep|awk '{print $1}')
    echo "old_pid=${old_pid}"
    if [ -z $old_pid ];then
        echo "Process Non-existent!"
        echo "Starting Process...."
        nohup python $script_name > $log_name 2>&1 &
    else
        kill -9 ${old_pid}
        mid_pid=$(ps ax|grep $1.py|grep -v grep|awk '{print $1}')
        if [ -z ${mid_pid} ];then
            echo "Process Close Success!"
            echo "Start Restarting....."
            nohup python $script_name > $log_name 2>&1 &
        else
            echo "Process Close Fail!"
            exit 1
        fi
    fi
    new_pid=$(ps ax|grep $1.py|grep -v grep|awk '{print $1}')
    if [ -z ${new_pid} ];then
        echo "Restart Fail!"
    else
        echo "Restart Success!"
        echo "new_pid=${new_pid}"
    fi
}

restart_service 'CodeStartPerception'