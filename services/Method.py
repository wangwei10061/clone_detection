# aim: this is the object of a method
# date: 2022-05-30
# author: zhangxunhui


class Method(object):
    def __init__(
        self,
        repo_id: int,
        ownername: str,
        reponame: str,
        commit_sha: str,
        filepath: bytes,
        start: int,
        end: int,
        tokens: list,
    ):
        self.repo_id = repo_id
        self.ownername = ownername
        self.reponame = reponame
        self.commit_sha = commit_sha
        self.filepath = filepath
        self.start = start
        self.end = end
        self.tokens = tokens
