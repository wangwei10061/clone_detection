# aim: to find which day has the most number of commits in total for the 100 selected popular projects
# author: zhangxunhui
# date: 2022-07-04

import os

from dulwich.objects import Blob, Commit, Tag, Tree
from dulwich.repo import Repo


def day_selection():
    repo_paths = []  # record all the repo paths
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
    print("finish reading all the repos' paths")

    commit_dict = {}  # key: commit_time, count of commits
    for repo_path in repo_paths:
        repo = Repo(repo_path)
        print("handling repo: {repo_path}".format(repo_path=repo_path))
        object_store = repo.object_store
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
                commit_time = (
                    obj.commit_time - obj.commit_timezone
                )  # get the utc time
                commit_dict.setdefault(commit_time, 0)
                commit_dict[commit_time] += 1
            else:
                raise Exception("Unknown type!")

    print("sorting commit dict")
    # sort the dict by commit_time asc
    sorted_commits = [
        (k, commit_dict[k]) for k in sorted(commit_dict.keys(), reverse=False)
    ]
    # use a day window to search for the most number of commits in the development history (86400 seconds)
    window_size = 86400
    max_num = 0
    max_start = 0
    max_end = 0
    print("finding the day with the most number of commits")
    for i in range(len(sorted_commits)):
        num = sorted_commits[i][1]
        start = sorted_commits[i][0]
        end = start + window_size - 1
        for j in range(i + 1, len(sorted_commits)):
            if sorted_commits[j][0] > end:
                break
            else:
                num += sorted_commits[j][1]
                if num > max_num:
                    max_num = num
                    max_start = start
                    max_end = end
    print("start time in seconds: {start}".format(start=max_start))
    print("end time in seconds: {end}".format(end=max_end))
    print("max commit num: {num}".format(num=max_num))


if __name__ == "__main__":
    day_selection()
    print("finish")
