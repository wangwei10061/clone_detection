# aim: The CodeStartPerception service for LSICCDS_server
# author: zhangxunhui
# date: 2022-04-23

import os
import sys
import time

from ChangedMethodExtractor import ChangedMethodExtractor
from dulwich.objects import Blob, Commit, Tag, Tree
from dulwich.repo import Repo
from dulwich.walk import WalkEntry
from ESUtils import ESUtils
from MySQLUtils import MySQLUtils
from utils import read_config


class HandleRepository(object):
    def __init__(self, repository_path, config):
        self.config = config
        self.repository_path = repository_path
        self.repo = Repo(self.repository_path)
        self.ownername = self.repo.path.split("/")[-2]
        self.reponame = self.repo.path.split("/")[-1].split(".")[0]
        self.mysql_utils = MySQLUtils(
            host=self.config["mysql"]["host"],
            port=self.config["mysql"]["port"],
            username=self.config["mysql"]["username"],
            password=self.config["mysql"]["password"],
            database=self.config["mysql"]["database"],
            autocommit=False,
            dictcursor=True,
        )
        self.repo_id = self.mysql_utils.get_repo_id(
            self.ownername, self.reponame
        )
        if self.repo_id is None:
            raise Exception(
                "HandleRepository Error: cannot find the id of repository: {repository_path}".format(
                    repository_path=self.repository_path
                )
            )
        else:
            self.repo_id = self.repo_id["id"]
        self.es_utils = ESUtils(config=self.config)
        read_handled_commits_start = time.time()
        self.handled_commits = self.es_utils.get_handled_commits(
            repo_id=self.repo_id,
            index_name=self.config["elasticsearch"]["index_handled_commits"],
        )
        print(
            "read handled commits time: {t}".format(
                t=time.time() - read_handled_commits_start
            )
        )  # this is very slow

    def run(self):
        """Get all the commits."""

        commits = []

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

        """Handle each commit."""
        for commit in commits:
            if commit.id.decode() in self.handled_commits:
                continue
            else:
                HandleCommit(
                    repo=self.repo,
                    repo_id=self.repo_id,
                    ownername=self.ownername,
                    reponame=self.reponame,
                    commit=commit,
                    config=self.config,
                    es_utils=self.es_utils,
                ).run()


class HandleCommit(object):
    def __init__(
        self,
        repo: Repo,
        repo_id: int,
        ownername: str,
        reponame: str,
        commit: Commit,
        config,
        es_utils: ESUtils,
    ):
        self.repo = repo
        self.repo_id = repo_id
        self.ownername = ownername
        self.reponame = reponame
        self.commit = commit
        self.config = config
        self.es_utils = es_utils

    def run(self):
        commit_sha = self.commit.id.decode()

        handle_one_commit_start = time.time()
        """Generate all the changes for this commit."""
        walk_entry = WalkEntry(
            self.repo.get_walker(include=[self.commit.id]), self.commit
        )
        t_changes = walk_entry.changes()  # get all the TreeChange objects
        if len(self.commit.parents) > 1:
            t_changes = [item for t_cs in t_changes for item in t_cs]
        print(
            "generate tree_changes: {t}".format(
                t=time.time() - handle_one_commit_start
            )
        )

        changed_methods = ChangedMethodExtractor(
            repo=self.repo,
            ownername=self.ownername,
            reponame=self.reponame,
            commit_sha=commit_sha,
            t_changes=t_changes,
            config=self.config,
        ).parse()

        es_data_bulk = self.es_utils.extract_es_infos(
            changed_methods=changed_methods
        )
        self.es_utils.insert_es_bulk(es_data_bulk)

        """Finish handling this commit, insert into the handled_commit index in es."""
        es_data = {"repo_id": self.repo_id, "commit_sha": commit_sha}
        self.es_utils.insert_es_item(
            item=es_data,
            index_name=self.config["elasticsearch"]["index_handled_commits"],
        )

        print(
            "handle_one_commit: {t}".format(
                t=time.time() - handle_one_commit_start
            )
        )


def handle_repositories(repositories_path: str, config: dict):
    """Handle all the repositories in the directory."""

    # iterate all the ownernames
    ownername_paths = [
        f.path for f in os.scandir(repositories_path) if f.is_dir()
    ]
    for ownername_path in ownername_paths:
        # iterate all the repositories
        reponame_git_paths = [
            f.path for f in os.scandir(ownername_path) if f.is_dir()
        ]
        for reponame_git_path in reponame_git_paths:
            if not reponame_git_path.endswith("dubbo.git"):
                continue  # only for test
            # handle one repository
            handler = HandleRepository(
                repository_path=reponame_git_path, config=config
            )
            handler.run()


def main():
    config_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "config.yml"
    )
    config = read_config(config_path)
    if config is None:
        print(
            "Error: configuration file {config_path} not found".format(
                config_path=config_path
            )
        )
        sys.exit(1)

    try:
        repositories_path = config["gitea"]["repositories_path"]
    except Exception:
        print("Error: gitea repositories_path configration not found")
        sys.exit(1)

    handle_repositories(repositories_path=repositories_path, config=config)


if __name__ == "__main__":
    main()
    print("Finish CodeStartPerception service")
