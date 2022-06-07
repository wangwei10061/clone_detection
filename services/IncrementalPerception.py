# aim: The IncrementalPerception service for LSICCDS_server
# author: zhangxunhui
# date: 2022-05-31

import os

from flask import Flask, request
from models.CommitInfo import CommitInfo
from RabbitmqUtils import RabbitmqUtils
from utils import read_config

app = Flask(__name__)

config_path = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "config.yml"
)
config = read_config(config_path)


@app.route("/LSICCDS_webhook", methods=["POST"])
def LSICCDS_incremental_api():
    event = request.environ.get("HTTP_X_GITEA_EVENT")
    unhandled_commits = []
    if event == "push":
        data = request.get_json()
        repo_id = data["repository"]["id"]
        ownername = data["repository"]["owner"]["login"]
        reponame = data["repository"]["name"]
        commits = data["commits"]
        for commit in commits:
            sha = commit["id"]
            commitInfo = CommitInfo(
                repo_id=repo_id,
                ownername=ownername,
                reponame=reponame,
                sha=sha,
            )
            unhandled_commits.append(commitInfo)

        # send unhandled commits to rabbitmq
        RabbitmqUtils(config=config).sendMsgs(
            queueName="unhandled_commits", msgs=unhandled_commits
        )
        return None
    else:
        print("Error with the setting of gitea system webhook!")
        return None


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
