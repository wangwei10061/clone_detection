# aim: The CodeStartPerception service for LSICCDS_server
# author: zhangxunhui
# date: 2022-04-23

import os
import sys

from dulwich.repo import Repo
from dulwich.walk import WalkEntry, Walker
from ObjectIdx import createObjectIdx
from ObjectPack import createObjectPack
from utils import read_config


def handle_pack(reponame_git_path: str):
    """Handle the pack file in a repository."""
    # whether pack file exists
    pack_folder = os.path.join(reponame_git_path, "objects/pack")
    pack_file_names = [
        name for name in os.listdir(pack_folder) if name.endswith(".pack")
    ]
    if len(pack_file_names) > 0:
        for pack_file_name in pack_file_names:
            idx_file_name = pack_file_name[:-4] + "idx"
            object_idx = createObjectIdx(
                filepath=os.path.join(pack_folder, idx_file_name)
            )
            object_pack = createObjectPack(
                object_idx=object_idx,
                filepath=os.path.join(pack_folder, pack_file_name),
            )
            print(object_pack)
    else:
        return


def handle_repositories(repositories_path: str):
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
            """Get all the commits.
            Commits are stored in three different ways:
            1. loose commits
            2. packed commits
            3. submodule commits
            4. lfs是否需要考虑
            有了dulwich以后只需要考虑commit的遍历以及每个commit与parent之间的变化就可以了
            """
            r = Repo(reponame_git_path)
            print(type(r))

            handle_pack(reponame_git_path=reponame_git_path)

            print("pause")


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

    handle_repositories(repositories_path=repositories_path)


if __name__ == "__main__":
    main()
    print("Finish CodeStartPerception service")
