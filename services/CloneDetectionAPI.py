# aim: this is used to define the restful api for clients
# date: 2022-05-28
# author: zhangxunhui

import json
import os

from ChangedMethodExtractor import ChangedMethodExtractor
from CloneDetection import CloneDetection
from dulwich.diff_tree import tree_changes
from dulwich.repo import Repo
from flask import Flask, request
from models.RepoInfo import RepoInfo
from MySQLUtils import MySQLUtils
from utils import read_config

app = Flask(__name__)


class HandlePR(object):
    def __init__(
        self,
        base_repo_id: int,
        head_repo_id: int,
        base_commit_sha: str,
        head_commit_sha: str,
    ):

        self.base_repo_id = base_repo_id
        self.head_repo_id = head_repo_id
        self.base_commit_sha = base_commit_sha
        self.head_commit_sha = head_commit_sha

        self.config_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "config.yml"
        )
        self.config = read_config(self.config_path)

        self.mysql_utils = MySQLUtils(
            host=self.config["mysql"]["host"],
            port=self.config["mysql"]["port"],
            username=self.config["mysql"]["username"],
            password=self.config["mysql"]["password"],
            database=self.config["mysql"]["database"],
            autocommit=False,
            dictcursor=True,
        )

        """Query mysql for owner_name and name of repository."""
        base_repo_info = self.mysql_utils.get_repo_info(repo_id=base_repo_id)
        base_repo_ownername = base_repo_info["owner_name"]
        base_repo_reponame = base_repo_info["name"]
        base_repo_path = os.path.join(
            self.config["gitea"]["repositories_path"],
            base_repo_ownername,
            base_repo_reponame + ".git",
        )
        self.baseRepoInfo = RepoInfo(
            repo_id=base_repo_id,
            ownername=base_repo_ownername,
            reponame=base_repo_reponame,
            repo_path=base_repo_path,
        )
        self.base_repo = Repo(self.baseRepoInfo.repo_path)

        head_repo_info = self.mysql_utils.get_repo_info(repo_id=head_repo_id)
        head_repo_ownername = head_repo_info["owner_name"]
        head_repo_reponame = head_repo_info["name"]
        head_repo_path = os.path.join(
            self.config["gitea"]["repositories_path"],
            head_repo_ownername,
            head_repo_reponame + ".git",
        )
        self.headRepoInfo = RepoInfo(
            repo_id=head_repo_id,
            ownername=head_repo_ownername,
            reponame=head_repo_reponame,
            repo_path=head_repo_path,
        )
        self.head_repo = Repo(self.headRepoInfo.repo_path)

    def extract_changed_methods(self):

        """Compare the diff between head_commit_sha and base_commit_sha.
        There are two cases:
        1. the head branch is not generated from base branch - base_commit_sha is not in the head repo, because using --allow-unrelated-histories
        2. the head branch is generated from base branch - base_commit_sha is in the head repo
        """

        if self.base_commit_sha.encode() not in self.head_repo:
            # this is the first case
            """The files in head repo are all newly added."""
            t_changes = tree_changes(
                self.head_repo.object_store,
                tree1_id=None,
                tree2_id=self.head_repo.object_store[
                    self.head_commit_sha.encode()
                ].tree,
            )
        else:
            # this is the second case
            t_changes = tree_changes(
                self.head_repo.object_store,
                tree1_id=self.head_repo.object_store[
                    self.base_commit_sha.encode()
                ].tree,
                tree2_id=self.head_repo.object_store[
                    self.head_commit_sha.encode()
                ].tree,
            )

        changed_methods = ChangedMethodExtractor(
            repo=self.head_repo,
            repoInfo=self.headRepoInfo,
            commit_sha=self.head_commit_sha,
            t_changes=t_changes,
            config=self.config,
        ).parse()
        return changed_methods

    def parse(self):
        """Find changed functions."""
        changed_methods = self.extract_changed_methods()
        """Do the clone detection."""
        result = CloneDetection(
            methods=changed_methods, config=self.config
        ).run()
        return result


@app.route("/clone_detection", methods=["POST"])
def clone_detection_api():
    data = request.get_json()
    if (
        "base_repo_id" not in data
        or "head_repo_id" not in data
        or "head_commit_sha" not in data
        or "base_commit_sha" not in data
    ):
        return "RESTful request error: repo_id or head_commit_sha or base_commit_sha parameter not found!"
    else:
        base_repo_id = data["base_repo_id"]
        if type(base_repo_id) != int:
            return "RESTful request error: base_repo_id should be an integer!"

        head_repo_id = data["head_repo_id"]
        if type(head_repo_id) != int:
            return "RESTful request error: head_repo_id should be an integer!"

        head_commit_sha = data["head_commit_sha"]
        if type(head_commit_sha) != str:
            return "RESTful request error: new commit shas should be a string!"

        base_commit_sha = data["base_commit_sha"]
        if type(base_commit_sha) != str:
            return "RESTful request error: old commit sha should be a string!"

        result = HandlePR(
            base_repo_id=base_repo_id,
            head_repo_id=head_repo_id,
            base_commit_sha=base_commit_sha,
            head_commit_sha=head_commit_sha,
        ).parse()

        return json.dumps(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
