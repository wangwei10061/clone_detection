# aim: find the new clones that cannot be found by NIL, as we have considered multiple versions.
# author: zhangxunhui
# date: 2022-07-28

import os
import queue
import subprocess
import sys
import threading
from typing import List

import pandas as pd
import pymysql
import yaml
from dulwich.objects import Blob, Commit, Tree
from dulwich.repo import Repo

REPOPATH = "test/test_accuracy_middle_results/Ant1.10.1"
THREADNUM = 1
tablename = "apache:ant"


class BlobInfo(object):
    def __init__(
        self,
        repo: Repo = None,
        commit: Commit = None,
        filepath: str = None,
        blob: Blob = None,
    ) -> None:
        self.repo = repo
        self.commit = commit
        self.filepath = filepath
        self.blob = blob


class MySQLOperator(object):
    def __init__(
        self, host: str, port: int, username: str, password: str, database: str
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.conn = self.connect(autocommit=False)
        self.cur = self.conn.cursor(pymysql.cursors.DictCursor)

    def connect(self, autocommit=True):
        conn = pymysql.connect(
            host=self.host,
            port=int(self.port),
            user=self.username,
            passwd=self.password,
            db=self.database,
            autocommit=autocommit,
        )
        return conn

    def create_blob_table(self, tablename):
        sql = """
            CREATE TABLE IF NOT EXISTS `LSICCDS_test`.`{tablename}`  (
                `id` int(11) NOT NULL AUTO_INCREMENT,
                `sha` varchar(255) NULL,
                `commit_sha` varchar(255) NULL,
                `filepath` varchar(255) NULL,
                PRIMARY KEY (`id`),
                INDEX(`sha`) USING BTREE,
                INDEX(`commit_sha`) USING BTREE,
                INDEX(`filepath`) USING BTREE
            );
        """.format(
            tablename=tablename
        )
        self.cur.execute(sql)
        self.conn.commit()
        print(
            "Finish creating table `{tablename}`".format(tablename=tablename)
        )

    def insert_blobInfos(self, tablename: str, blobInfos: List[BlobInfo]):
        for blobInfo in blobInfos:
            self.cur.execute(
                "insert into `{tablename}` (sha, commit_sha, filepath) values (%s, %s, %s)".format(
                    tablename=tablename
                ),
                (
                    blobInfo.blob.id.decode(),
                    blobInfo.commit.id,
                    blobInfo.filepath,
                ),
            )
        self.conn.commit()

    def is_commit_handled(self, tablename: str, commit_sha: str):
        self.cur.execute(
            "select * from `{tablename}` where commit_sha=%s".format(
                tablename=tablename
            ),
            (commit_sha,),
        )
        result = self.cur.fetchone()
        return result is not None

    def get_handled_commits(self, tablename: str) -> List[str]:
        self.cur.execute(
            "select distinct commit_sha from `{tablename}`".format(
                tablename=tablename
            )
        )
        result = self.cur.fetchall()
        result = [item["commit_sha"] for item in result]
        return result

    def get_java_blobs(self, tablename: str) -> List[str]:
        self.cur.execute(
            "select distinct sha from `{tablename}` where filepath like '%{filepath}'".format(
                tablename=tablename, filepath=".java"
            )
        )
        result = self.cur.fetchall()
        result = [item["sha"] for item in result]
        return result

    def get_java_blobs_4_commit(
        self, tablename: str, commit_sha: str
    ) -> List[str]:
        self.cur.execute(
            "select distinct sha from `{tablename}` where filepath like '%{filepath}' and commit_sha='{commit_sha}'".format(
                tablename=tablename, filepath=".java", commit_sha=commit_sha
            )
        )
        result = self.cur.fetchall()
        result = [item["sha"] for item in result]
        return result

    def create_clone_table(self, tablename):
        sql = """
            DROP TABLE IF EXISTS `LSICCDS_test`.`{tablename}`;
        """.format(
            tablename=tablename
        )
        self.cur.execute(sql)

        sql = """
            CREATE TABLE IF NOT EXISTS `LSICCDS_test`.`{tablename}`  (
                `id` int(0) NOT NULL AUTO_INCREMENT,
                `blob_sha_1` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
                `start_1` int(0) NULL DEFAULT NULL,
                `end_1` int(0) NULL DEFAULT NULL,
                `blob_sha_2` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
                `start_2` int(0) NULL DEFAULT NULL,
                `end_2` int(0) NULL DEFAULT NULL,
                PRIMARY KEY (`id`) USING BTREE,
                INDEX `blob_sha_1`(`blob_sha_1`) USING BTREE,
                INDEX `start_1`(`start_1`) USING BTREE,
                INDEX `end_1`(`end_1`) USING BTREE,
                INDEX `blob_sha_2`(`blob_sha_2`) USING BTREE,
                INDEX `start_2`(`start_2`) USING BTREE,
                INDEX `end_2`(`end_2`) USING BTREE
            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
        """.format(
            tablename=tablename
        )
        self.cur.execute(sql)
        self.conn.commit()
        print(
            "Finish creating table `{tablename}`".format(tablename=tablename)
        )

    def insert_clone_pairs(
        self, tablename: str, df: pd.DataFrame, relfolder: str
    ):
        def convert_sha(sha):
            return os.path.relpath(
                sha,
                os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), relfolder
                ),
            )[:-5]

        df["blob_sha_1"] = df["blob_sha_1"].apply(convert_sha)
        df["blob_sha_2"] = df["blob_sha_2"].apply(convert_sha)
        for i, row in df.iterrows():
            self.cur.execute(
                "insert into `{tablename}` (blob_sha_1, start_1, end_1, blob_sha_2, start_2, end_2) values (%s, %s, %s, %s, %s, %s)".format(
                    tablename=tablename
                ),
                (
                    row["blob_sha_1"],
                    int(row["start_1"]),
                    int(row["end_1"]),
                    row["blob_sha_2"],
                    int(row["start_2"]),
                    int(row["end_2"]),
                ),
            )
            if i % 1000 == 0:
                self.conn.commit()
        self.conn.commit()
        print(
            "Finish inserting clone pairs into {tablename}".format(
                tablename=tablename
            )
        )


def download_target_project():
    target_dir = "test/test_accuracy_middle_results"
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    if not os.path.exists(os.path.join(target_dir, "Ant1.10.1")):
        p = subprocess.Popen(
            "cd "
            + target_dir
            + " && git clone git@github.com:apache/ant.git Ant1.10.1"
            + " && cd Ant1.10.1 && git checkout tags/rel/1.10.1",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        _ = p.stdout.read().decode("utf-8", errors="replace")
        _ = p.wait()
    print("Finish downloading target project!")


def find_blobs_in_tree(
    repo: Repo, commit: Commit, tree: Tree, relpath: bytes = b""
) -> List[BlobInfo]:
    result = []
    for entry in tree.items():
        obj = repo.object_store[entry.sha]
        new_relpath = os.path.join(relpath, entry.path)
        if obj.type_name == b"blob":
            result.append(
                BlobInfo(
                    repo=repo, commit=commit, filepath=new_relpath, blob=obj
                )
            )
        else:
            new_tree = obj
            result.extend(
                find_blobs_in_tree(
                    repo=repo,
                    commit=commit,
                    tree=new_tree,
                    relpath=new_relpath,
                )
            )
    return result


def extract_blob_relations(repo_path: str) -> dict:
    """
    return:
        - {key: Blob.id, value: [BlobInfo]}, as each blob may belong to many commits
    """
    result = {}
    commits: Commit = []
    repo = Repo(repo_path)
    object_shas = list(repo.object_store)
    for object_sha in object_shas:
        obj = repo.object_store[object_sha]
        if obj.type_name == b"commit":
            # this is a commit
            commits.append(obj)
    for commit in commits:
        blobInfos = find_blobs_in_tree(
            repo=repo, commit=commit, tree=repo.object_store[commit.tree]
        )
        for blobInfo in blobInfos:
            result.setdefault(blobInfo.blob.id, [])
            result[blobInfo.blob.id].append(blobInfo)
    return result


def extract_commits(repo_path: str) -> List[Commit]:
    commits: Commit = []
    repo = Repo(repo_path)
    object_shas = list(repo.object_store)
    for object_sha in object_shas:
        obj = repo.object_store[object_sha]
        if obj.type_name == b"commit":
            # this is a commit
            commits.append(obj)
    return commits


def extract_blobs(repo_path: str) -> List[Blob]:
    blobs: Blob = []
    repo = Repo(repo_path)
    object_shas = list(repo.object_store)
    for object_sha in object_shas:
        obj = repo.object_store[object_sha]
        if obj.type_name == b"blob":
            # this is a blob
            blobs.append(obj)
    return blobs


def extract_source_files(mysqlOp: MySQLOperator):

    repo = Repo(REPOPATH)

    """
    read java files and related blob shas
    """
    # blob_shas = mysqlOp.get_java_blobs(tablename=tablename)
    # # copy and rename source files for LSICCDS
    # target_folder = "test/test_accuracy_middle_results/LSICCDS_blobs"
    # if not os.path.exists(target_folder):
    #     os.makedirs(target_folder)
    # for sha in blob_shas:
    #     with open(os.path.join(target_folder, sha + ".java"), 'wb') as f:
    #         f.write(repo.object_store[sha.encode()].data)

    latest_commit = repo.object_store[repo.head()]
    blob_shas = mysqlOp.get_java_blobs_4_commit(
        tablename=tablename, commit_sha=latest_commit.id.decode()
    )
    # copy and rename source files for NIL
    target_folder = "test/test_accuracy_middle_results/NIL_blobs"
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
    for sha in blob_shas:
        with open(os.path.join(target_folder, sha + ".java"), "wb") as f:
            f.write(repo.object_store[sha.encode()].data)
    print("Finish extracting source files!")


def test_find_blobs_in_tree():
    repo = Repo(REPOPATH)
    commit = repo.object_store[b"e003f5e0c16f9e7a8081a56829b16784c19553e9"]
    tree = repo.object_store[commit.tree]
    blobs = find_blobs_in_tree(repo, commit, tree)
    filepaths = []
    for blob in blobs:
        filepath = blob.filepath.decode()
        filepaths.append(filepath)

    filepaths_2 = []
    for root, directories, files in os.walk(REPOPATH):
        for name in files:
            if ".git" in root:
                continue
            relpath = os.path.relpath(
                root, "test/test_accuracy_middle_results/Ant1.10.1"
            )
            if relpath == ".":
                relpath = ""
            filepaths_2.append(os.path.join(relpath, name))

    filepaths.sort()
    filepaths_2.sort()

    print(" ".join(filepaths) == " ".join(filepaths_2))


class HandleOneCommitThread(threading.Thread):
    def __init__(self, name: str, q: queue.Queue, mysqlOp: MySQLOperator):
        threading.Thread.__init__(self)
        self.name = name
        self.q = q
        self.repo = Repo(REPOPATH)
        self.mysqlOp = mysqlOp

    def run(self):
        print("[Info]: Start thread: " + self.name)
        while not self.q.empty():
            commit_sha = self.q.get()
            commit = self.repo.object_store[commit_sha.encode()]
            blobInfos = find_blobs_in_tree(
                repo=self.repo,
                commit=commit,
                tree=self.repo.object_store[commit.tree],
            )
            # insert results into table
            self.mysqlOp.insert_blobInfos(
                tablename=tablename, blobInfos=blobInfos
            )
            self.q.task_done()
        print("[Info]: Exist thread: " + self.name)


if __name__ == "__main__":

    # download the repository
    download_target_project()

    with open("test/config.yml", "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    # create table for test
    mysqlOp = MySQLOperator(
        host=config["mysql"]["host"],
        port=int(config["mysql"]["port"]),
        username=config["mysql"]["username"],
        password=config["mysql"]["password"],
        database=config["mysql"]["database"],
    )
    mysqlOp.create_blob_table(tablename)

    # # extract all commits
    # commits = extract_commits(repo_path=REPOPATH)
    # handled_commits = mysqlOp.get_handled_commits(tablename=tablename)
    # all_commits = [commit.id.decode() for commit in commits]
    # unhandled_commits = list(set(all_commits) - set(handled_commits))

    # workQueue = queue.Queue()
    # for commit_sha in unhandled_commits:
    #     workQueue.put(commit_sha)

    # threads = []
    # for i in range(THREADNUM):
    #     t = HandleOneCommitThread(
    #         name="Thread-" + str(i + 1),
    #         q=workQueue,
    #         mysqlOp=MySQLOperator(
    #             host=config['mysql']['host'],
    #             port=int(config['mysql']['port']),
    #             username=config['mysql']['username'],
    #             password=config['mysql']['password'],
    #             database=config['mysql']['database']
    #         )
    #     )
    #     t.start()
    #     threads.append(t)
    # for t in threads:
    #     t.join()
    # print("Finish extracting blob commit relations!")

    # # extract source code into target folder
    # extract_source_files(mysqlOp=mysqlOp)

    # # invoke NIL for clone detection
    # p = subprocess.Popen(
    #     "cd test/test_accuracy_middle_results/NIL_blobs && java -jar /home/zxh/programs/LSICCDS/LSICCDS_server/test/NIL.jar -s {FakeTargetDir} -mit 50 -mil 6 -t 8".format(
    #         FakeTargetDir="./"
    #     ),
    #     shell=True,
    #     stdout=subprocess.PIPE,
    #     stderr=subprocess.STDOUT,
    # )
    # output = p.stdout.read().decode("utf-8", errors="replace")
    # _ = p.wait()
    # print("Finish clone detection for NIL!")

    # p = subprocess.Popen(
    #     "cd test/test_accuracy_middle_results/LSICCDS_blobs && java -jar /home/zxh/programs/LSICCDS/LSICCDS_server/test/NIL.jar -s {FakeTargetDir} -mit 50 -mil 6 -t 8".format(
    #         FakeTargetDir="./"
    #     ),
    #     shell=True,
    #     stdout=subprocess.PIPE,
    #     stderr=subprocess.STDOUT,
    # )
    # output = p.stdout.read().decode("utf-8", errors="replace")
    # _ = p.wait()
    # print("Finish clone detection for LSICCDS!")

    # # extract clone paris into database
    # df = pd.read_csv("test/test_accuracy_middle_results/NIL_blobs/result_5_10_70.csv", header=None, index_col=None)
    # df.columns = ['blob_sha_1', 'start_1', 'end_1', 'blob_sha_2', 'start_2', 'end_2']
    # mysqlOp.create_clone_table(tablename=tablename + ":nil")
    # mysqlOp.insert_clone_pairs(tablename=tablename + ":nil", df=df, relfolder="test_accuracy_middle_results/NIL_blobs")

    df = pd.read_csv(
        "test/test_accuracy_middle_results/LSICCDS_blobs/result_5_10_70.csv",
        header=None,
        index_col=None,
    )
    df.columns = [
        "blob_sha_1",
        "start_1",
        "end_1",
        "blob_sha_2",
        "start_2",
        "end_2",
    ]
    mysqlOp.create_clone_table(tablename=tablename + ":lsiccds")
    mysqlOp.insert_clone_pairs(
        tablename=tablename + ":lsiccds",
        df=df,
        relfolder="test_accuracy_middle_results/LSICCDS_blobs",
    )

    # What does the methods in clone pairs in NIL_blobs called in previous blob versions?
    # 哪些是没有发生改变的？把没变的找出来以后，我们就可以统计出变化的或者检测不到的clone占比是多少了。
