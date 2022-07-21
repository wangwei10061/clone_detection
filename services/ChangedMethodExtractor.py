# aim: this is used to extract changed function contents from two code snippets
# date: 2022-05-30
# author: zhangxunhui

from difflib import SequenceMatcher
from typing import List

from dulwich.diff_tree import TreeChange
from dulwich.objects import Commit
from dulwich.repo import Repo
from models.MethodInfo import MethodInfo
from models.RepoInfo import RepoInfo

from services.parser.FuncExtractor import FuncExtractor
from services.utils import is_file_supported


class ChangedMethodExtractor(object):
    """How two commits diff from each other.
    init params are:
        - commit_sha is the commit that introduces the new changed method, however we also use this class to handle prs. So the commit_sha also represents the head_commit_sha rather than the exact commit that introduces the new changed method.
    We assume that different t_changes may modify the same file to be compatible with merge change
    """

    def __init__(
        self,
        repo: Repo,
        repoInfo: RepoInfo,
        commit: Commit,
        t_changes: List[TreeChange],
        config,
    ):
        self.repo = repo
        self.repoInfo = repoInfo
        self.commit = commit
        self.commit_sha = self.commit.id.decode()
        self.t_changes = t_changes
        self.config = config

    def find_related_method_indexes(
        self,
        old_method: MethodInfo,
        old_line_relation: dict,
        new_line_method_dict: dict,
    ):
        start = old_method.start
        end = old_method.end
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
        return changed_new_method_indexes

    def extract_diff(self, old_content: list, new_content: list):
        """Only store new lines for insert and replace; only store old lines for delete.
        We also need to store the line number relationship between old and new file, {
            old line number: [new line numbers] # because there may not be strict line number relationship
        }
        """
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
        return changed_lines_new, changed_lines_old, old_line_relation

    def extract_changed_funcs_4new(
        self, key_new: bytes, changed_lines_new: list
    ):
        key_new_tuple = key_new.split(b":")
        filepath = key_new_tuple[0]
        object_sha = key_new_tuple[1]
        # read file content
        content = self.repo.object_store[object_sha].data
        # read all the methods, and line method index relationship
        new_methods, new_line_method_dict = FuncExtractor(
            repoInfo=self.repoInfo,
            commit=self.commit,
            filepath=filepath,
            content=content,
            config=self.config,
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
        return changed_methods

    def extract_changed_funcs_4old(
        self,
        key_old: bytes,
        key_new: bytes,
        changed_lines_old: list,
        changed_lines_new: list,
        old_line_relation: dict,
    ):
        """Handle related new file change at the same time."""
        """Get all the methods in new path."""
        key_new_tuple = key_new.split(b":")
        new_filepath = key_new_tuple[0]
        new_object_sha = key_new_tuple[1]
        new_content = self.repo.object_store[new_object_sha].data
        new_methods, new_line_method_dict = FuncExtractor(
            repoInfo=self.repoInfo,
            commit=self.commit,
            filepath=new_filepath,
            content=new_content,
            config=self.config,
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
            repoInfo=self.repoInfo,
            commit=self.commit,
            filepath=old_filepath,
            content=old_content,
            config=self.config,
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
        return changed_methods

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

        return changed_lines_old, changed_lines_new, old_line_relation

    def parse(self):

        changes_new = (
            {}
        )  # record all the changes_new, key: relative filepath:objsha; value: set() changed lines
        changes_old = (
            {}
        )  # record all the changes_old, key: relative filepath:objsha; value: set() changed lines
        old_line_relation_all = (
            {}
        )  # record the old line number and new line number relationship

        for t_change in self.t_changes:

            (
                changed_lines_old,
                changed_lines_new,
                old_line_relation,
            ) = self.handle_tree_change(t_change)

            if changed_lines_new is None:
                # no new lines added
                pass
            else:
                key_new = t_change.new.path + b":" + t_change.new.sha
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
                            )  # this case should not occur
                        else:
                            # this case should not occur
                            pass

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
        for key_new, changed_lines_new in changes_new.items():
            if key_new in handled_key_new:
                continue  # already handled when handling the related old file
            changed_methods.extend(
                self.extract_changed_funcs_4new(
                    key_new=key_new, changed_lines_new=changed_lines_new
                )
            )

        return changed_methods
