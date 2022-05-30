# aim: this is used to define the restful api for clients
# date: 2022-05-28
# author: zhangxunhui

import os
from difflib import SequenceMatcher

from dulwich.repo import Repo
from flask import Flask, request
from MySQLUtils import MySQLUtils
from utils import read_config

app = Flask(__name__)

config_path = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "config.yml"
)
config = read_config(config_path)

mysql_utils = MySQLUtils(
    host=config["mysql"]["host"],
    port=config["mysql"]["port"],
    username=config["mysql"]["username"],
    password=config["mysql"]["password"],
    database=config["mysql"]["database"],
    autocommit=False,
    dictcursor=True,
)


def extract_diff(old_content: list, new_content: list):
    changed_new_lines = []  # record all the changed lines for the new file
    for tag, _, _, j1, j2 in SequenceMatcher(
        None, old_content, new_content
    ).get_opcodes():
        if tag == "equal":
            pass
        elif tag == "insert" or tag == "replace":
            changed_new_lines.extend([i for i in range(j1 + 1, j2 + 1)])
        elif tag == "delete":
            pass
        else:
            raise Exception("type error")
    return changed_new_lines


def extract_changed_funcs(
    repo: Repo, base_commit_sha: str, new_commit_shas: list
):
    all_parents = []  # store all the parent commit shas
    for new_commit_sha in new_commit_shas:
        commit = repo.object_store[new_commit_sha.encode()]
        parents = commit.parents
        parents = [parent.decode() for parent in parents]
        all_parents.extend(parents)
    # find the new_commits that are not regarded as parent
    lastest_new_commits = [
        new_commit_sha
        for new_commit_sha in new_commit_shas
        if new_commit_sha not in all_parents
    ]

    # compare the diff between lastest_new_commits and base_commit_sha
    # for
    # changed_new_lines = self.extract_diff(
    #     old_content=self.repo.object_store[
    #         tree_change.old.sha
    #     ].data.split(b"\n"),
    #     new_content=self.repo.object_store[
    #         tree_change.new.sha
    #     ].data.split(b"\n"),
    # )
    print(lastest_new_commits)


@app.route("/clone_detection", methods=["POST"])
def clone_detection():
    data = request.get_json()
    if (
        "repo_id" not in data
        or "new_commit_shas" not in data
        or "base_commit_sha" not in data
    ):
        return "RESTful request error: repo_id or new_commit_shas or base_commit_sha parameter not found!"
    else:
        repo_id = data["repo_id"]
        if type(repo_id) != int:
            return "RESTful request error: repo_id should be an integer!"

        new_commit_shas = data["new_commit_shas"]
        if type(new_commit_shas) != list:
            return "RESTful request error: new commit shas should be a list!"

        base_commit_sha = data["base_commit_sha"]
        if type(base_commit_sha) != str:
            return "RESTful request error: old commit sha should be a string!"

        """Query mysql for owner_name and name of repository."""
        repo_info = mysql_utils.get_repo_info(repo_id=repo_id)
        ownername = repo_info["owner_name"]
        reponame = repo_info["name"]
        repo_path = os.path.join(
            config["gitea"]["repositories_path"], ownername, reponame + ".git"
        )
        repo = Repo(repo_path)
        print(str(repo))

        """Find changed files and related changed methods."""

        """Extract the n-grams."""
        return new_commit_shas


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
