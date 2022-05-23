# aim: The CodeStartPerception service for LSICCDS_server
# author: zhangxunhui
# date: 2022-04-23

import os
import sys
from difflib import SequenceMatcher
from parser.FuncExtractor import FuncExtractor

from dulwich.diff_tree import TreeChange
from dulwich.objects import Blob, Commit, Tag, Tree
from dulwich.repo import Repo
from dulwich.walk import WalkEntry
from utils import read_config


class HandleRepository(object):
    def __init__(self, repository_path) -> None:
        self.repository_path = repository_path
        self.repo = Repo(self.repository_path)

    def handle_tree_change(self, tree_change: TreeChange):
        """
        get the changed relative filepath and changed lines of a TreeChange object
        return:
        changed_path: b'', changed_new_lines: list
        None, None # if there is no change
        """
        changed_path = None
        changed_new_lines = None
        change_type = tree_change.type
        if change_type == "add":
            changed_new_lines = self.extract_diff(
                old_content=[],
                new_content=self.repo.object_store[
                    tree_change.new.sha
                ].data.split(b"\n"),
            )
            changed_path = tree_change.new.path
        elif change_type == "modify":
            changed_new_lines = self.extract_diff(
                old_content=self.repo.object_store[
                    tree_change.old.sha
                ].data.split(b"\n"),
                new_content=self.repo.object_store[
                    tree_change.new.sha
                ].data.split(b"\n"),
            )
            changed_path = tree_change.new.path
        elif change_type == "delete":
            pass
        else:
            raise Exception("type error")
        if changed_new_lines is not None and len(changed_new_lines) == 0:
            changed_new_lines = None
            changed_path = None
        return changed_path, changed_new_lines

    def extract_diff(self, old_content: list, new_content: list):
        changed_new_lines = []  # record all the changed lines for the new file
        for tag, _, _, j1, j2 in SequenceMatcher(
            None, old_content, new_content
        ).get_opcodes():
            if tag == "equal" or tag == "delete":
                pass
            elif tag == "insert" or tag == "replace":
                changed_new_lines.extend([i for i in range(j1 + 1, j2 + 1)])
            else:
                raise Exception("type error")
        return changed_new_lines

    def extract_n_grams(self, tokens: list, n=5):
        ngrams = []
        for i in range(0, len(tokens) - n + 1):
            ngram = (" ".join(tokens[i : i + n])).lower()
            ngrams.append(ngram)
        return ngrams

    def run(self):
        """Get all the commits."""

        commit_shas = []
        commits = []

        object_store = self.repo.object_store
        object_shas = list(iter(object_store))
        for object_sha in object_shas:
            obj = object_store[object_sha]
            if isinstance(obj, Tag):
                pass
            elif isinstance(obj, Blob):
                pass
            elif isinstance(obj, Commit):
                commits.append(obj)
                commit_shas.append(object_sha)
            elif isinstance(obj, Tree):
                pass
            else:
                raise Exception("error type")

        for commit in commits:
            parents = commit.parents
            walk_entry = WalkEntry(
                self.repo.get_walker(include=[commit.id]), commit
            )
            tree_changes = (
                walk_entry.changes()
            )  # get all the TreeChange objects
            # handle each TreeChange, for parents > 1, handle each TreeChange list
            changes = (
                {}
            )  # record all the changes, key: relative filepath:objsha; value: set() changed lines
            if len(parents) > 1:
                for t_changes in tree_changes:
                    for t_change in t_changes:
                        changed_path, changed_lines = self.handle_tree_change(
                            t_change
                        )
                        if (
                            changed_path is not None
                            and changed_lines is not None
                        ):
                            changes.setdefault(
                                changed_path + b":" + t_change.new.sha, set()
                            )
                            changes[
                                changed_path + b":" + t_change.new.sha
                            ] = set(
                                changes[changed_path + ":" + t_change.new.sha]
                            ).union(
                                set(changed_lines)
                            )
            else:
                for t_change in tree_changes:
                    changed_path, changed_lines = self.handle_tree_change(
                        t_change
                    )
                    if changed_path is not None and changed_lines is not None:
                        changes.setdefault(
                            changed_path + b":" + t_change.new.sha, set()
                        )
                        changes[changed_path + b":" + t_change.new.sha] = set(
                            changes[changed_path + b":" + t_change.new.sha]
                        ).union(set(changed_lines))

            # handle all the changes
            for path_sha, line_set in changes.items():
                path_sha_tuple = path_sha.split(b":")
                filepath = path_sha_tuple[0]
                object_sha = path_sha_tuple[1]
                # read file content
                content = self.repo.object_store[object_sha].data
                # read all the methods, and line method index relationship
                methods, line_method_dict = FuncExtractor(
                    filepath=filepath, content=content
                ).parse_file()
                # extract the changed methods
                changed_method_indexes = list(
                    set([line_method_dict[line] for line in line_set])
                )
                changed_methods = [
                    methods[index] for index in changed_method_indexes
                ]
                # for changed methods, extract N-Gram list
                for changed_method in changed_methods:
                    ngrams = self.extract_n_grams(changed_method["tokens"])
                    # update the inverted index of elastic search
                    print(ngrams)
            print("pause")


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
            # handle one repository
            handler = HandleRepository(repository_path=reponame_git_path)
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

    handle_repositories(repositories_path=repositories_path)


if __name__ == "__main__":
    main()
    print("Finish CodeStartPerception service")
