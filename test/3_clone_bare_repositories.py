# aim: clone the bare repositories of the 100 repos in 1 step
# author: zhangxunhui
# date: 2022-06-22

import json
import subprocess


def clone_repos():
    with open("test/1_search_popular_active_projects.json", "r") as f:
        projects = json.load(f)

    for project in projects:
        ownername = project["owner"]["login"]
        reponame = project["name"]
        ssh_url = project["ssh_url"]

        print(ssh_url)

        p = subprocess.Popen(
            args="git clone --bare {ssh_url} test/bare_repos/{ownername}/{reponame}".format(
                ssh_url=ssh_url, ownername=ownername, reponame=reponame
            ),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        p.communicate()


if __name__ == "__main__":
    clone_repos()
    print("finish")
