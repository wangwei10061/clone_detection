# aim: the self-defined class of commit, which is used to store the received commit information
# date: 2022-06-07
# author: zhangxunhui

from models.QueueTaskInfo import QueueTaskInfo


class CommitInfo(QueueTaskInfo):
    type: str = "commit_info"

    def __init__(self, repo_id: int, ownername: str, reponame: str, sha: str):
        super().__init__(self.type)

        self.repo_id = repo_id
        self.ownername = ownername
        self.reponame = reponame
        self.sha = sha
