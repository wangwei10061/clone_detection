# aim: insert fake commit tasks into rabbitmq
# author: zhangxunhui
# date: 2022-07-18

import json
import os
import queue
import sys
import threading
import time

import yaml

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)
sys.path.append(os.path.join(parentdir, "services"))

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dulwich.repo import Repo

from services.ColdStartPerception import HandleCommit
from services.ESUtils import ESUtils
from services.models.CommitInfo import CommitInfo
from services.models.RepoInfo import RepoInfo
from services.utils import read_config

with open("test/config.yml", "r") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

service_config_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    "services/config.yml",
)
service_config = read_config(service_config_path)

num_tasks = -1

THREADNUM = 1

recorder_file = "test/7_{threadNum}_result".format(threadNum=THREADNUM)

q = queue.Queue()  # record the inflate indices of fake_commitInfos


def read_fake_commits():
    results = []
    with open("test/6_fake_commitInfos.json", "r") as f:
        data = json.loads(f.read())
        for obj_dict in data:
            obj = CommitInfo.dict2obj(obj_dict)
            results.append(obj)
    print("finish reading commits!")
    return results


class IncrementalPerceptionHandler(threading.Thread):
    def __init__(self, name, q, fake_commitInfos):
        threading.Thread.__init__(self)
        self.name = name
        self.q = q
        self.fake_commitInfos = fake_commitInfos
        self.es_utils = ESUtils(config=service_config)

    def run(self):
        print("[Info]: Start thread: " + self.name)
        while not self.q.empty():
            commitInfo = self.fake_commitInfos[self.q.get()]
            repo_path = os.path.join(
                config["gitea_repo_path"],
                commitInfo.ownername.lower(),
                commitInfo.reponame.lower() + ".git",
            )
            repoInfo = RepoInfo(
                repo_path=repo_path,
                repo_id=commitInfo.repo_id,
                ownername=commitInfo.ownername,
                reponame=commitInfo.reponame,
            )
            repo = Repo(repoInfo.repo_path)
            commit = repo.object_store[commitInfo.sha.encode()]

            HandleCommit(
                repo=repo,
                repoInfo=repoInfo,
                commit=commit,
                config=service_config,
                es_utils=self.es_utils,
            ).run()
            self.q.task_done()
        print("[Info]: Exist thread: " + self.name)


class TriggerManager(object):
    def __init__(self):
        pass

    @classmethod
    def interval_trigger(cls, conf):
        time_args = {"s": 0, "m": 0, "h": 0, "d": 0, "w": 0}

        time_unit = conf["timeUnit"]
        time_interval = conf["timeInterval"]
        time_args[time_unit] = time_interval

        return IntervalTrigger(
            seconds=time_args["s"],
            minutes=time_args["m"],
            hours=time_args["h"],
            days=time_args["d"],
            weeks=time_args["w"],
            timezone=pytz.utc,
        )


def cal_remained_tasks():
    handled_num = num_tasks - q.qsize()
    # write the results of records into a file
    with open(recorder_file, "a") as f:
        f.write(str(handled_num) + "\n")


if __name__ == "__main__":

    # delete the result file
    if os.path.exists(recorder_file):
        os.remove(recorder_file)
    with open(recorder_file, "a") as f:
        f.write(str(0) + "\n")

    # clean the elasticsearch and create new indices
    n_gram_index_name = service_config["elasticsearch"]["index_ngram"]
    handled_commit_index_name = service_config["elasticsearch"][
        "index_handled_commits"
    ]
    es_utils = ESUtils(config=service_config)
    es_utils.delete_index(n_gram_index_name)
    es_utils.create_n_gram_index()
    es_utils.delete_index(handled_commit_index_name)
    es_utils.create_handled_commit_index()

    fake_commitInfos = read_fake_commits()
    for i in range(len(fake_commitInfos)):
        for _ in range(20):  # 105254
            q.put(i)
            if q.qsize() > 1000:  # this is for test
                break
        if q.qsize() > 1000:  # this is for test
            break
    num_tasks = q.qsize()

    # run the handler and record the remained tasks
    scheduler = BackgroundScheduler()
    trigger = TriggerManager.interval_trigger(
        conf={"timeInterval": 5, "timeUnit": "s"}
    )
    scheduler.add_job(cal_remained_tasks, trigger, id="1")
    scheduler.start()

    threads = []
    for i in range(THREADNUM):
        t = IncrementalPerceptionHandler(
            name="Thread-" + str(i + 1), q=q, fake_commitInfos=fake_commitInfos
        )
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    print("finish testing thread num: {threadNum}".format(threadNum=THREADNUM))
