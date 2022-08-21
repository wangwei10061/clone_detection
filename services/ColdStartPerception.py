# aim: The ColdStartPerception service for LSICCDS_server
# author: zhangxunhui
# date: 2022-04-23

import os
import queue
import sys
import threading
from typing import List

from ChangedMethodExtractor import ChangedMethodExtractor
from dulwich.objects import Blob, Commit, Tag, Tree
from dulwich.repo import Repo
from dulwich.walk import WalkEntry
from ESUtils import ESUtils
from models.RepoInfo import RepoInfo
from MySQLUtils import MySQLUtils

from services.utils import read_config


class HandleRepository(object):
    def __init__(self, repoInfo: RepoInfo, config: dict, es_utils: ESUtils):
        self.config = config
        self.repoInfo = repoInfo
        self.repo = Repo(self.repoInfo.repo_path)
        self.repoInfo.ownername = self.repo.path.split("/")[-2]
        self.repoInfo.reponame = self.repo.path.split("/")[-1].split(".")[0]
        self.mysql_utils = MySQLUtils(
            host=self.config["mysql"]["host"],
            port=self.config["mysql"]["port"],
            username=self.config["mysql"]["username"],
            password=self.config["mysql"]["password"],
            database=self.config["mysql"]["database"],
            autocommit=False,
            dictcursor=True,
        )
        repo_id = self.mysql_utils.get_repo_id(
            self.repoInfo.ownername, self.repoInfo.reponame
        )
        if repo_id is None:
            raise Exception(
                "HandleRepository Error: cannot find the id of repository: {repository_path}".format(
                    repository_path=self.repository_path
                )
            )
        else:
            self.repoInfo.repo_id = repo_id["id"]
        self.es_utils = es_utils
        self.handled_commits = self.es_utils.get_handled_commits(
            repo_id=self.repoInfo.repo_id,
            index_name=self.config["elasticsearch"]["index_handled_commits"],
        )

    def run(self):
        """Get all the commits."""

        print(
            "[Info]: Handling repository {repo_path}".format(
                repo_path=self.repo.path
            )
        )

        commits: List[Commit] = []

        object_store = self.repo.object_store
        object_shas = list(iter(object_store))
        for object_sha in object_shas:
            obj = object_store[object_sha]
            if (
                isinstance(obj, Tag)
                or isinstance(obj, Blob)
                or isinstance(obj, Tree)
            ):
                pass
            elif isinstance(obj, Commit):
                commits.append(obj)
            else:
                raise Exception("HandleRepository.run Error: unknown type!")

        """Whether this repository is forked or original"""
        info = self.mysql_utils.get_repo_info(repo_id=self.repoInfo.repo_id)
        is_fork = False
        if info is not None and info["is_fork"] == 1:
            is_fork = True
        if is_fork:
            # eliminate the forked commits
            fork_id = info["fork_id"]
            origin_info = self.mysql_utils.get_repo_info(repo_id=fork_id)
            if origin_info is not None:
                origin_ownername = origin_info["owner_name"]
                origin_reponame = origin_info["name"]
                origin_repo_path = os.path.join(
                    self.config["gitea"]["repositories_path"],
                    origin_ownername,
                    origin_reponame + ".git",
                )
                origin_repo = Repo(origin_repo_path)
                origin_commits: List[Commit] = []
                origin_object_store = origin_repo.object_store
                origin_object_shas = list(iter(origin_object_store))
                for object_sha in origin_object_shas:
                    obj = origin_object_store[object_sha]
                    if isinstance(obj, Commit):
                        origin_commits.append(obj)
                commits = list(set(commits) - set(origin_commits))
            else:
                pass  # origin repo not found in gitea mysql database
        else:
            pass  # not a fork repo

        """Handle each commit."""
        for commit in commits:
            HandleCommit(
                repo=self.repo,
                repoInfo=self.repoInfo,
                commit=commit,
                config=self.config,
                es_utils=self.es_utils,
            ).run()


class HandleRepoThread(threading.Thread):
    def __init__(
        self,
        name: str,
        q: queue.Queue,
        config: dict,
    ):
        threading.Thread.__init__(self)
        self.name = name
        self.q = q
        self.config = config
        self.es_utils = ESUtils(config=self.config)

    def run(self):
        print("[Info]: Start thread: " + self.name)
        while not self.q.empty():
            repoInfo = self.q.get()
            # handle one repository
            handler = HandleRepository(
                repoInfo=repoInfo,
                config=self.config,
                es_utils=self.es_utils,
            )
            handler.run()
            self.q.task_done()
        print("[Info]: Exist thread: " + self.name)


class HandleCommit(object):
    def __init__(
        self,
        repo: Repo,
        repoInfo: RepoInfo,
        commit: Commit,
        config: dict,
        es_utils: ESUtils,
    ):
        self.repo = repo
        self.repoInfo = repoInfo
        self.commit = commit
        self.config = config
        self.es_utils = es_utils

    def run(self):
        commit_sha = self.commit.id.decode()
        print(
            "[Info]: Handling commit {commit_sha}".format(
                commit_sha=commit_sha
            )
        )

        """Generate all the changes for this commit."""
        walk_entry = WalkEntry(
            self.repo.get_walker(include=[self.commit.id]), self.commit
        )
        t_changes = walk_entry.changes()  # get all the TreeChange objects
        if len(self.commit.parents) > 1:
            t_changes = [item for t_cs in t_changes for item in t_cs]

        changed_methods = ChangedMethodExtractor(
            repo=self.repo,
            repoInfo=self.repoInfo,
            commit=self.commit,
            t_changes=t_changes,
            config=self.config,
        ).parse()

        es_data_bulk = self.es_utils.extract_es_infos(
            changed_methods=changed_methods
        )
        self.es_utils.insert_es_bulk(es_data_bulk)

        """Finish handling this commit, insert into the handled_commit index in es."""
        es_data = {"repo_id": self.repoInfo.repo_id, "commit_sha": commit_sha}
        self.es_utils.insert_es_item(
            item=es_data,
            index_name=self.config["elasticsearch"]["index_handled_commits"],
        )


def handle_repositories(repositories_path: str, config: dict):
    """Handle all the repositories in the directory."""

    es_utils = ESUtils(config=config)
    es_utils.create_n_gram_index()
    es_utils.create_handled_commit_index()

    """Handle repositories by multiple threads."""
    workQueue = queue.Queue()

    # iterate all the ownernames
    ownername_paths = [
        f.path for f in os.scandir(repositories_path) if f.is_dir()
    ]
    for ownername_path in ownername_paths:
        # iterate all the repositories
        repo_git_paths = [
            f.path for f in os.scandir(ownername_path) if f.is_dir()
        ]
        for repo_git_path in repo_git_paths:
            # if "test1.git" not in repo_git_path:
            #     continue  # only for test

            workQueue.put(RepoInfo(repo_path=repo_git_path))

    THREADNUM = config["coldstart_service"]["THREADNUM"]
    threads = []
    for i in range(THREADNUM):
        t = HandleRepoThread(
            name="Thread-" + str(i + 1),
            q=workQueue,
            config=config,
        )
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


def main():
    config_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "config.yml"
    )
    config = read_config(config_path)
    if config is None:
        print(
            "[Error]: configuration file {config_path} not found".format(
                config_path=config_path
            )
        )
        sys.exit(1)

    try:
        repositories_path = config["gitea"]["repositories_path"]
    except Exception:
        print("[Error]: gitea repositories_path configration not found")
        sys.exit(1)

    handle_repositories(repositories_path=repositories_path, config=config)


if __name__ == "__main__":
    main()
    print("Finish ColdStartPerception service")
