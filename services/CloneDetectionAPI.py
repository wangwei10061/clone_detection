# aim: this is used to define the restful api for clients
# date: 2022-05-28
# author: zhangxunhui

import json
import os
from urllib.parse import urljoin

import requests
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
        pr_id: int,
        base_repo_id: int,
        head_repo_id: int,
        base_commit_sha: str,
        head_commit_sha: str,
    ):

        self.pr_id = pr_id
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

        self.head_commit = self.head_repo.object_store[
            self.head_commit_sha.encode()
        ]
        self.base_commit = self.base_repo.object_store[
            self.base_commit_sha.encode()
        ]

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
            commit=self.head_commit,
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

    def return_result(self, result: dict):
        clone_item = """
        File: {filepath} - {start_line} ~ {end_line}
        Clone from:
        - Repository: {ownername}/{reponame}
        - Commit: {commit_sha}
        - File: {filepath_clone}
        - lines: {start_line_clone} ~ {end_line_clone}\n
        """
        body = ""
        for method_str, clones in result.items():
            clone = clones[0]
            repo_id = clone["repo_id"]
            clone_repo_info = self.mysql_utils.get_repo_info(repo_id=repo_id)
            if clone_repo_info is None:
                continue
            ms = json.loads(method_str)
            filepath = ms["filepath"]
            start_line = ms["start"]
            end_line = ms["end"]
            ownername = clone_repo_info["owner_name"]
            reponame = clone_repo_info["name"]
            commit_sha = clone["commit_sha"]
            filepath_clone = clone["filepath"]
            start_line_clone = clone["start_line"]
            end_line_clone = clone["end_line"]
            body += clone_item.format(
                filepath=filepath,
                start_line=start_line,
                end_line=end_line,
                ownername=ownername,
                reponame=reponame,
                commit_sha=commit_sha,
                filepath_clone=filepath_clone,
                start_line_clone=start_line_clone,
                end_line_clone=end_line_clone,
            )

        if len(body) == 0:
            return

        token = self.config["client_service"]["token"]
        headers = {
            "Authorization": "token " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        gitea_url = self.config["client_service"]["gitea_url"]
        url = urljoin(
            gitea_url,
            "api/v1/repos/{owner}/{repo}/issues/{index}/comments".format(
                owner=self.baseRepoInfo.ownername,
                repo=self.baseRepoInfo.reponame,
                index=self.pr_id,
            ),
        )

        result = requests.post(
            url=url, data=json.dumps({"body": body}), headers=headers
        )
        if result.status_code != 201:
            print("Error: create repository error")


@app.route("/clone_detection", methods=["POST"])
def clone_detection_api():
    data = request.get_json()
    if data["action"] == "opened":
        if "pull_request" not in data:
            return {"Query": "No need for prediction!"}
        else:
            pr_id = data["pull_request"]["id"]
            base = data["pull_request"]["base"]
            head = data["pull_request"]["head"]

            base_repo_id = base["repo_id"]
            head_repo_id = head["repo_id"]

            base_commit_sha = base["sha"]
            head_commit_sha = head["sha"]

            prHandler = HandlePR(
                pr_id=pr_id,
                base_repo_id=base_repo_id,
                head_repo_id=head_repo_id,
                base_commit_sha=base_commit_sha,
                head_commit_sha=head_commit_sha,
            )
            result = prHandler.parse()

            # return by comment api
            if len(result) > 0:
                prHandler.return_result(result=result)
            return {"Query": "Success!"}

    else:
        return {"Query": "No need for prediction!"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
