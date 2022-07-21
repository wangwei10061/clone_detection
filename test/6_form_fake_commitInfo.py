# aim: find all the commits and form into fake commitInfo objects
# author: zhangxunhui
# date: 2022-07-17
"""
commitInfo = CommitInfo(
    repo_id=repo_id,
    ownername=ownername,
    reponame=reponame,
    sha=sha,
)
start time in seconds: 1490759292
end time in seconds: 1490845691
"""
import json
import os
import sys

import yaml

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)
sys.path.append(os.path.join(parentdir, "services"))

from dulwich.repo import Repo
from utils import find_bare_repos

from services.models.CommitInfo import CommitInfo
from services.MySQLUtils import MySQLUtils
from services.utils import read_config

with open("test/config.yml", "r") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

service_config_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    "services/config.yml",
)
service_config = read_config(service_config_path)

ownername = "test_performance"


def find_commits(start_time=1490759292, end_time=1490845691):
    # find all the commits
    commitList = []
    repo_paths = []  # record all the repo paths
    repo_names = []  # record all the repo names
    root_path = "dependencies/gitea/git/repositories/test_performance"
    for root, directories, _ in os.walk(root_path):
        for directory in directories:
            if not directory.endswith(".git"):
                continue
            abs_directory = os.path.join(root, directory)
            repo_name = directory[:-4]
            repo_paths.append(abs_directory)
            repo_names.append(repo_name)
    print("finish reading all the repos' paths")
    for i in range(len(repo_paths)):
        repo_path = repo_paths[i]
        repo_name = repo_names[i]
        repo = Repo(repo_path)
        print("handling repo: {repo_path}".format(repo_path=repo_path))

        mysql_utils = MySQLUtils(
            host=service_config["mysql"]["host"],
            port=service_config["mysql"]["port"],
            username=service_config["mysql"]["username"],
            password=service_config["mysql"]["password"],
            database=service_config["mysql"]["database"],
            autocommit=False,
            dictcursor=True,
        )
        repo_id = mysql_utils.get_repo_id(
            ownername=ownername, reponame=repo_name
        )["id"]

        shas = list(iter(repo.object_store))
        for sha in shas:
            object = repo.object_store[sha]
            if object.type_name.decode() != "commit":
                continue  # only handle commits
            else:
                commit_time = (
                    object.commit_time - object.commit_timezone
                )  # get the utc time
                if commit_time >= start_time and commit_time <= end_time:
                    commitInfo = CommitInfo(
                        repo_id=repo_id,
                        ownername=ownername,
                        reponame=repo_name,
                        sha=sha.decode(),
                    )
                    commitList.append(commitInfo.__dict__)

    # put commits into a json file
    with open("test/6_fake_commitInfos.json", "w") as f:
        json.dump(commitList, f)
    print("finish forming faking commit infos")


if __name__ == "__main__":
    find_commits()
    print("finish")
