# This file is used to create apis for performance test
# author: zhangxunhui
# date: 2022-07-14

import json
import os
import subprocess

import requests
import yaml
from dulwich.repo import Repo

base_url = "http://8.130.51.51:3000/api/v1"

with open("test/config.yml", "r") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

headers = {
    "Authorization": "token " + config["gitea_token"],
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def get_api(url):
    result = requests.get(url)
    return result


def find_bare_repos():
    repo_paths = []  # record all the repo paths
    repo_names = []  # record all the repo names
    root_path = "test/bare_repos"
    for root, directories, _ in os.walk(root_path):
        for directory in directories:
            abs_directory = os.path.join(root, directory)
            for root2, directories2, _ in os.walk(abs_directory):
                if (
                    os.path.relpath(root2, root_path).count(os.sep) > 0
                ):  # this is not the second level
                    continue
                for directory2 in directories2:
                    repo_paths.append(os.path.join(root2, directory2))
                    repo_names.append(directory2)
    print("finish reading all the repos' paths")
    return repo_paths, repo_names


def upload_projects(login="test_performance"):
    repo_paths, repo_names = find_bare_repos()

    for i in range(len(repo_paths)):
        repo_path = repo_paths[i]
        repo_name = repo_names[i]
        print("handling repo: {repo_path}".format(repo_path=repo_path))
        """Whether the ownername/reponame already existed in GitLink."""
        result = get_api(
            url=os.path.join(
                base_url,
                "repos/{ownername}/{reponame}".format(
                    ownername=login, reponame=repo_name
                ),
            )
        )
        if result.status_code == 200:
            # delete the repository
            delete_project(ownername=login, reponame=repo_name)
        # create the repository
        create_project(reponame=repo_name)

        # upload the bare repository
        origin_url = (
            "http://8.130.51.51:3000/{ownername}/{reponame}.git".format(
                ownername=login, reponame=repo_name
            )
        )
        subprocess.Popen(
            "cd "
            + repo_path
            + " && git remote set-url origin "
            + origin_url
            + " && git push http://{ownername}:{password}@8.130.51.51:3000/{ownername}/{reponame}.git --all".format(
                ownername=login,
                password=config["gitea_password"],
                reponame=repo_name,
            ),
            stdout=subprocess.PIPE,
            shell=True,
        )

    print("Finish uploading bare repositories!")


def delete_project(ownername, reponame):
    url = os.path.join(
        base_url,
        "repos/{ownername}/{reponame}".format(
            ownername=ownername, reponame=reponame
        ),
    )
    requests.delete(url=url, headers=headers)


def create_project(reponame):
    url = os.path.join(base_url, "user/repos")
    body = {"name": reponame}
    result = requests.post(url=url, data=json.dumps(body), headers=headers)
    if result.status_code != 201:
        print("Error: create repository error")


def create_branches(login="test_performance", branchname="LSICCDS_test"):
    repo_paths, repo_names = find_bare_repos()

    for i in range(len(repo_paths)):
        repo_path = repo_paths[i]
        repo_name = repo_names[i]
        print("handling repo: {repo_path}".format(repo_path=repo_path))
        """Whether the branch of the target repository already existed in GitLink."""
        result = get_api(
            url=os.path.join(
                base_url,
                "repos/{ownername}/{reponame}/branches/{branchname}".format(
                    ownername=login, reponame=repo_name, branchname=branchname
                ),
            )
        )
        if result.status_code == 200:
            # delete the branch
            delete_branch(
                ownername=login, reponame=repo_name, branchname=branchname
            )
        # create the branch
        create_branch(
            ownername=login, reponame=repo_name, branchname=branchname
        )


def delete_branch(ownername, reponame, branchname):
    url = os.path.join(
        base_url,
        "repos/{ownername}/{reponame}/branches/{branchname}".format(
            ownername=ownername, reponame=reponame, branchname=branchname
        ),
    )
    requests.delete(url=url, headers=headers)


def create_branch(ownername, reponame, branchname):
    url = os.path.join(
        base_url, "repos/{ownername}/{reponame}/branches"
    ).format(ownername=ownername, reponame=reponame)
    body = {"new_branch_name": branchname}
    result = requests.post(url=url, data=json.dumps(body), headers=headers)
    if result.status_code != 201:
        print("Error: create repository error")


if __name__ == "__main__":
    create_branches()
    print("finish")
