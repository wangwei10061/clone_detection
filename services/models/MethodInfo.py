# aim: this is the object of a method
# date: 2022-05-30
# author: zhangxunhui


class MethodInfo(object):
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

        if "commit_sha" in kwargs:
            self.commit_sha = kwargs["commit_sha"]
        else:
            self.commit_sha = None

        if "filepath" in kwargs:
            self.filepath = kwargs["filepath"]
        else:
            self.filepath = None

        if "start" in kwargs:
            self.start = kwargs["start"]
        else:
            self.start = None

        if "end" in kwargs:
            self.end = kwargs["end"]
        else:
            self.end = None

        if "tokens" in kwargs:
            self.tokens = kwargs["tokens"]
        else:
            self.tokens = None

        if "ngrams" in kwargs:
            self.ngrams = kwargs["ngrams"]
        else:
            self.ngrams = None
