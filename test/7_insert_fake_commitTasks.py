# aim: insert fake commit tasks into rabbitmq
# author: zhangxunhui
# date: 2022-07-18

import json
import os
import sys
from typing import List

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)
sys.path.append(os.path.join(parentdir, "services"))

from services.models.CommitInfo import CommitInfo
from services.RabbitmqUtils import RabbitmqUtils
from services.utils import read_config

service_config_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    "services/config.yml",
)
service_config = read_config(service_config_path)
queueName = "unhandled_commits"


def purge_mq():
    RabbitmqUtils(config=service_config).purgeMQ(queueName=queueName)
    print("finish purging queue")


def read_fake_commits():
    results = []
    with open("test/6_fake_commitInfos.json", "r") as f:
        data = json.loads(f.read())
        for obj_dict in data:
            obj = CommitInfo.dict2obj(obj_dict)
            results.append(obj)
    return results


def insert_commits(unhandled_commits: List[CommitInfo]):
    # ceil(10525321/100) = 105254
    for i in range(105254):
        RabbitmqUtils(config=service_config).sendMsgs(
            queueName=queueName, msgs=unhandled_commits
        )
        print("finish inserting the {i}th round!".format(i=i))
    print("finish inserting commits into the queue!")


if __name__ == "__main__":
    purge_mq()
    insert_commits(read_fake_commits())
    print("finish")
