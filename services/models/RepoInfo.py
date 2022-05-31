# aim: this is the object of a repo
# date: 2022-05-31
# author: zhangxunhui


class RepoInfo(object):
    def __init__(
        self,
        **kwargs,
    ):
        if "repo_id" in kwargs:
            self.repo_id = kwargs["repo_id"]
        else:
            self.repo_id = None

        if "ownername" in kwargs:
            self.ownername = kwargs["ownername"]
        else:
            self.ownername = None

        if "reponame" in kwargs:
            self.reponame = kwargs["reponame"]
        else:
            self.reponame = None

        if "repo_path" in kwargs:
            self.repo_path = kwargs["repo_path"]
        else:
            self.repo_path = None


if __name__ == "__main__":
    r = RepoInfo()
    repo_id = r.repo_id
    print("finish")
