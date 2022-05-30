# aim: The CodeStartPerception service for LSICCDS_server
# author: zhangxunhui
# date: 2022-04-23

import os
import sys
import time
from difflib import SequenceMatcher
from parser.FuncExtractor import FuncExtractor

from dulwich.diff_tree import TreeChange
from dulwich.objects import Blob, Commit, Tag, Tree
from dulwich.repo import Repo
from dulwich.walk import WalkEntry
from ESUtils import ESUtils
from MySQLUtils import MySQLUtils
from utils import is_file_supported, read_config


class HandleRepository(object):
    def __init__(self, repository_path, config) -> None:
        self.config = config
        self.repository_path = repository_path
        self.repo = Repo(self.repository_path)
        self.ownername = self.repo.path.split("/")[-2]
        self.reponame = self.repo.path.split("/")[-1].split(".")[0]
        self.mysql_utils = MySQLUtils(
            host=self.config["mysql"]["host"],
            port=self.config["mysql"]["port"],
            username=self.config["mysql"]["username"],
            password=self.config["mysql"]["password"],
            database=self.config["mysql"]["database"],
            autocommit=False,
            dictcursor=True,
        )
        self.repo_id = self.mysql_utils.get_repo_id(
            self.ownername, self.reponame
        )
        if self.repo_id is None:
            raise Exception(
                "HandleRepository Error: cannot find the id of repository: {repository_path}".format(
                    repository_path=self.repository_path
                )
            )
        else:
            self.repo_id = self.repo_id["id"]
        self.es_utils = ESUtils(self.config["elasticsearch"]["urls"])
        read_handled_commits_start = time.time()
        self.handled_commits = self.es_utils.get_handled_commits(
            repo_id=self.repo_id,
            index_name=self.config["elasticsearch"]["index_handled_commits"],
        )
        print(
            "read handled commits time: {t}".format(
                t=time.time() - read_handled_commits_start
            )
        )  # this is very slow

    def handle_tree_change(self, tree_change: TreeChange):
        """
        get the changed relative filepath and changed lines of a TreeChange object
        return:
        changed_new_path: b'', changed_lines_new: list, changed_old_path: b'', changed_lines_old: list
        None, None, None, None # if there is no change
        """
        changed_lines_new = []
        changed_lines_old = []
        old_line_relation = {}

        start_time = time.time()
        change_type = tree_change.type
        if change_type == "add" and is_file_supported(
            tree_change.new.path.decode(),
            self.config["service"]["lang_suffix"],
        ):
            (
                changed_lines_new,
                changed_lines_old,
                old_line_relation,
            ) = self.extract_diff(
                old_content=[],
                new_content=self.repo.object_store[
                    tree_change.new.sha
                ].data.split(b"\n"),
            )
        elif change_type == "delete":
            pass  # the file is deleted, no need to consider anymore
        elif change_type == "modify" and is_file_supported(
            tree_change.new.path.decode(),
            self.config["service"]["lang_suffix"],
        ):
            (
                changed_lines_new,
                changed_lines_old,
                old_line_relation,
            ) = self.extract_diff(
                old_content=self.repo.object_store[
                    tree_change.old.sha
                ].data.split(b"\n"),
                new_content=self.repo.object_store[
                    tree_change.new.sha
                ].data.split(b"\n"),
            )
        elif not is_file_supported(
            tree_change.new.path.decode(),
            self.config["service"]["lang_suffix"],
        ):
            pass
        else:
            raise Exception(
                "HandleRepository.handle_tree_change error: change type is not support, should be add, modify or delete!"
            )

        if type(changed_lines_new) == list and len(changed_lines_new) == 0:
            changed_lines_new = None
        if type(changed_lines_old) == list and len(changed_lines_old) == 0:
            changed_lines_old = None

        print("handle_tree_change: {t}".format(t=time.time() - start_time))

        return changed_lines_old, changed_lines_new, old_line_relation

    def extract_diff(self, old_content: list, new_content: list):
        """Only store new lines for insert and replace; only store old lines for delete.
        We also need to store the line number relationship between old and new file, {
            old line number: [new line numbers] # because there may not be strict line number relationship
        }
        """
        start_time = time.time()
        old_line_relation = (
            {}
        )  # record the line number's relationship between old and new files
        changed_lines_new = []  # record all the changed lines for the new file
        changed_lines_old = []  # record all the deleted lines for the old file
        for tag, i1, i2, j1, j2 in SequenceMatcher(
            None, old_content, new_content
        ).get_opcodes():
            if tag == "equal":
                for i in range(i2 - i1):
                    old_line = i1 + i + 1
                    new_line = j1 + i + 1
                    old_line_relation[old_line] = [new_line]
            elif tag == "insert":
                changed_lines_new.extend([i for i in range(j1 + 1, j2 + 1)])
            elif tag == "delete":
                changed_lines_old.extend([i for i in range(i1 + 1, i2 + 1)])
                for i in range(i2 - i1):
                    old_line = i1 + i + 1
                    new_lines = []
                    old_line_relation[old_line] = new_lines
            elif tag == "replace":
                changed_lines_old.extend([i for i in range(i1 + 1, i2 + 1)])
                changed_lines_new.extend([i for i in range(j1 + 1, j2 + 1)])
                for i in range(i2 - i1):
                    old_line = i1 + i + 1
                    new_lines = [j + 1 for j in range(j1, j2)]
                    old_line_relation[old_line] = new_lines
            else:
                raise Exception("Function extract_diff Error: type error!")
        print("extract_diff: {t}".format(t=time.time() - start_time))
        return changed_lines_new, changed_lines_old, old_line_relation

    def extract_n_grams(self, tokens: list, n=5):
        ngrams = []
        for i in range(0, len(tokens) - n + 1):
            ngram = (" ".join(tokens[i : i + n])).lower()
            ngrams.append(ngram)
        return ngrams

    def extract_es_infos(self, commit_sha, changed_methods):
        es_data_bulk = []  # used to store the extracted change
        # for changed methods, extract N-Gram list
        for changed_method in changed_methods:
            ngrams = self.extract_n_grams(changed_method["tokens"])
            # update the inverted index of elastic search
            for ngram in ngrams:
                es_data = {
                    "_index": self.config["elasticsearch"]["index_ngram"],
                    "doc_as_upsert": True,
                    "doc": {
                        "ownername": self.ownername,
                        "reponame": self.reponame,
                        "commit_sha": commit_sha,
                        "filepath": changed_method["filepath"].decode(),
                        "start_line": changed_method["start"],
                        "end_line": changed_method["end"],
                        "gram": ngram,
                    },
                }
                es_data_bulk.append(es_data)
        return es_data_bulk

    def find_related_method_indexes(
        self, old_method, old_line_relation, new_line_method_dict
    ):
        start_time = time.time()
        start = old_method["start"]
        end = old_method["end"]
        changed_new_method_indexes = []
        for old_line in range(start, end + 1):
            new_lines = old_line_relation[old_line]
            if (
                len(new_lines) > 0
            ):  # there may exist cases, where old line is deleted and no new line related
                for new_line in new_lines:
                    if new_line in new_line_method_dict:
                        changed_new_method_indexes.append(
                            new_line_method_dict[new_line]
                        )
        print(
            "find_related_method_indexes: {t}".format(
                t=time.time() - start_time
            )
        )
        return changed_new_method_indexes

    def extract_changed_funcs_4new(self, key_new, changed_lines_new):
        start_time = time.time()
        key_new_tuple = key_new.split(b":")
        filepath = key_new_tuple[0]
        object_sha = key_new_tuple[1]
        # read file content
        content = self.repo.object_store[object_sha].data
        # read all the methods, and line method index relationship
        new_methods, new_line_method_dict = FuncExtractor(
            filepath=filepath, content=content, config=self.config
        ).parse_file()
        # extract the changed methods
        changed_method_indexes = list(
            set(
                [
                    new_line_method_dict[line]
                    for line in changed_lines_new
                    if line in new_line_method_dict
                ]
            )
        )
        changed_methods = [
            new_methods[index] for index in changed_method_indexes
        ]
        print(
            "extract_changed_funcs_4new: {t}".format(
                t=time.time() - start_time
            )
        )
        return changed_methods

    def extract_changed_funcs_4old(
        self,
        key_old,
        key_new,
        changed_lines_old,
        changed_lines_new,
        old_line_relation,
    ):
        """Handle related new file change at the same time."""
        """Get all the methods in new path."""
        start_time = time.time()
        key_new_tuple = key_new.split(b":")
        new_filepath = key_new_tuple[0]
        new_object_sha = key_new_tuple[1]
        new_content = self.repo.object_store[new_object_sha].data
        new_methods, new_line_method_dict = FuncExtractor(
            filepath=new_filepath, content=new_content, config=self.config
        ).parse_file()

        changed_new_method_indexes = [
            new_line_method_dict[line]
            for line in changed_lines_new
            if line in new_line_method_dict
        ]

        """Get all the methods in old path."""
        key_old_tuple = key_old.split(b":")
        old_filepath = key_old_tuple[0]
        old_object_sha = key_old_tuple[1]
        old_content = self.repo.object_store[old_object_sha].data
        old_methods, old_line_method_dict = FuncExtractor(
            filepath=old_filepath, content=old_content, config=self.config
        ).parse_file()

        """Extract changed old methods."""
        changed_old_methods = []
        for changed_line_old in changed_lines_old:
            if (
                changed_line_old in old_line_method_dict
            ):  # there may be cases where the method of the changed line is ignored just because the function is too small
                changed_old_methods.append(
                    old_line_method_dict[changed_line_old]
                )
        changed_old_methods = [
            old_methods[method_index]
            for method_index in set(changed_old_methods)
        ]

        """Which new method does changed old method related to."""
        for old_method in changed_old_methods:
            related_new_method_indexes = self.find_related_method_indexes(
                old_method=old_method,
                old_line_relation=old_line_relation,
                new_line_method_dict=new_line_method_dict,
            )

            changed_new_method_indexes.extend(related_new_method_indexes)

        changed_methods = [
            new_methods[index] for index in set(changed_new_method_indexes)
        ]
        print(
            "extract_changed_funcs_4old: {t}".format(
                t=time.time() - start_time
            )
        )
        return changed_methods

    def handle_one_commit(self, commit: Commit):
        commit_sha = commit.id.decode()
        if commit_sha in self.handled_commits:
            return  # already handled this commit

        handle_one_commit_start = time.time()
        """Generate all the changes for this commit."""
        walk_entry = WalkEntry(
            self.repo.get_walker(include=[commit.id]), commit
        )
        tree_changes = walk_entry.changes()  # get all the TreeChange objects
        if len(commit.parents) > 1:
            tree_changes = [item for t_cs in tree_changes for item in t_cs]
        print(
            "generate tree_changes: {t}".format(
                t=time.time() - handle_one_commit_start
            )
        )

        changes_new = (
            {}
        )  # record all the changes_new, key: relative filepath:objsha; value: set() changed lines
        changes_old = (
            {}
        )  # record all the changes_old, key: relative filepath:objsha; value: set() changed lines
        old_line_relation_all = (
            {}
        )  # record the old line number and new line number relationship

        for t_change in tree_changes:
            t_change_start = time.time()
            if type(t_change) != TreeChange:
                raise Exception(
                    "HandleRepository.handle_one_commit Error: TreeChange is not the right type!"
                )
            (
                changed_lines_old,
                changed_lines_new,
                old_line_relation,
            ) = self.handle_tree_change(t_change)
            if changed_lines_new is None:
                # delete file option
                pass
            else:
                key_new = t_change.new.path + b":" + t_change.new.sha
                # record all the changed lines
                if changed_lines_new is not None:
                    changes_new.setdefault(key_new, set())
                    changes_new[key_new] = set(changes_new[key_new]).union(
                        set(changed_lines_new)
                    )
                if changed_lines_old is not None:
                    key_old = t_change.old.path + b":" + t_change.old.sha
                    changes_old.setdefault(key_old, set())
                    changes_old[key_old] = set(changes_old[key_old]).union(
                        set(changed_lines_old)
                    )
                    # record the old line relation
                    old_line_relation_all.setdefault(key_old, {})
                    old_line_relation_all[key_old].setdefault(key_new, {})
                    for old_line, new_lines in old_line_relation.items():
                        if (
                            old_line
                            not in old_line_relation_all[key_old][key_new]
                        ):
                            old_line_relation_all[key_old][key_new][
                                old_line
                            ] = new_lines
                        elif old_line in changed_lines_old:
                            old_line_relation_all[key_old][key_new][
                                old_line
                            ] = list(
                                set(
                                    old_line_relation_all[key_old][key_new][
                                        old_line
                                    ]
                                ).union(set(new_lines))
                            )  # this may not occur
                        else:
                            pass
            print(
                "handle one tree change: {t}".format(
                    t=time.time() - t_change_start
                )
            )

        """Extract the changed functions in old file."""
        changed_methods = []
        handled_key_new = []
        for key_old, changed_lines_old in changes_old.items():
            key_new = list(old_line_relation_all[key_old].keys())[0]
            if key_new in changes_new:
                changed_lines_new = changes_new[key_new]
            else:
                changed_lines_new = set()
            handled_key_new.append(key_new)
            changed_methods.extend(
                self.extract_changed_funcs_4old(
                    key_old=key_old,
                    key_new=key_new,
                    changed_lines_old=changed_lines_old,
                    changed_lines_new=changed_lines_new,
                    old_line_relation=old_line_relation_all[key_old][key_new],
                )
            )

        """Extract the changed functions in new file."""
        for key_new, changed_lines_old in changes_new.items():
            if key_new in handled_key_new:
                continue  # already handled when handling the related old file
            changed_methods.extend(
                self.extract_changed_funcs_4new(
                    key_new=key_new, changed_lines_new=changed_lines_new
                )
            )

        es_data_bulk = self.extract_es_infos(
            commit_sha=commit_sha, changed_methods=changed_methods
        )
        start_time = time.time()
        self.es_utils.insert_es_bulk(es_data_bulk)
        print("insert_es_bulk: {t}".format(t=time.time() - start_time))

        """Finish handling this commit, insert into the handled_commit index in es."""
        es_data = {"repo_id": self.repo_id, "commit_sha": commit_sha}
        start_time = time.time()
        self.es_utils.insert_es_item(
            item=es_data,
            index_name=self.config["elasticsearch"]["index_handled_commits"],
        )
        print("insert_es_item: {t}".format(t=time.time() - start_time))

        print(
            "handle_one_commit: {t}".format(
                t=time.time() - handle_one_commit_start
            )
        )

    def run(self):
        """Get all the commits."""

        commits = []

        object_store = self.repo.object_store
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
                commits.append(obj)
            else:
                raise Exception("HandleRepository.run Error: unknown type!")

        """Handle each commit."""

        for commit in commits:
            self.handle_one_commit(commit)


def handle_repositories(repositories_path: str, config: dict):
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
            if not reponame_git_path.endswith("dubbo.git"):
                continue  # only for test
            # handle one repository
            handler = HandleRepository(
                repository_path=reponame_git_path, config=config
            )
            handler.run()


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

    handle_repositories(repositories_path=repositories_path, config=config)


if __name__ == "__main__":
    main()
    print("Finish CodeStartPerception service")
