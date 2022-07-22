# /bin/bash
# Used to test different number of threats with a limited time
# author: zhangxunhui
# date: 2022-07-22

COUNTTIME=120 # each program run X seconds
APPNAME="7_incremental_test.py"



function killProcess() {
    NAME=$1
    PID=$(ps -ef | grep $NAME | awk '{print $2}')
    echo "PID: $PID"
    kill -9 $PID
}

threats=(1 3 5)
for t in ${threats[@]}
do
    echo "run test with $t threats"
    now=`date +'%Y-%m-%d %H:%M:%S'`
    start_time=$(date --date="$now" +%s);


    nohup ~/anaconda3/envs/LSICCDS_server/bin/python -u test/7_incremental_test.py $t > test/7_incremental_test.log 2>&1 &

    while true
    do
        now=`date +'%Y-%m-%d %H:%M:%S'`
        end_time=$(date --date="$now" +%s);
        gap=$((end_time-start_time))
        if [ "$gap" -gt "$COUNTTIME" ]
        then
            killProcess $APPNAME
            break
        else
            sleep 1
        fi
    done
done
