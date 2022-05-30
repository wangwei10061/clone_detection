# aim: this is used to extract changed function contents from two code snippets
# date: 2022-05-30
# author: zhangxunhui

from difflib import SequenceMatcher
from parser.FuncExtractor import FuncExtractor

from dulwich.diff_tree import TreeChange
from utils import is_file_supported


class ChangedFuncExtractor(object):
    """How code2 change according to code1."""

    def __init__(self, tree_change: TreeChange, config):
        self.tree_change = tree_change
        self.config = config

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

    def extract_changed_funcs_4new(self, key_new, changed_lines_new):
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
        return changed_methods

    def parse(self):
        new_entry = self.tree_change.new
        old_entry = self.tree_change.old
        change_type = self.tree_change.type

        changed_methods = []

        if change_type == "add" and is_file_supported(
            new_entry.path.decode(), self.config["service"]["lang_suffix"]
        ):
            (
                changed_lines_new,
                changed_lines_old,
                old_line_relation,
            ) = self.extract_diff(
                old_content=[],
                new_content=self.repo.object_store[new_entry.sha].data.split(
                    b"\n"
                ),
            )
            key_new = new_entry.path + b":" + new_entry.sha
            changed_methods = self.extract_changed_funcs_4new(
                key_new=key_new, changed_lines_new=changed_lines_new
            )
        elif change_type == "delete":
            pass
        elif change_type == "modify" and is_file_supported(
            new_entry.path.decode(), self.config["lang_suffix"]
        ):
            (
                changed_lines_new,
                changed_lines_old,
                old_line_relation,
            ) = self.extract_diff(
                old_content=self.repo.object_store[old_entry.sha].data.split(
                    b"\n"
                ),
                new_content=self.repo.object_store[new_entry.sha].data.split(
                    b"\n"
                ),
            )
            key_old = old_entry.path + b":" + old_entry.sha
            changed_methods = self.extract_changed_funcs_4old(
                key_old=key_old,
                changed_lines_old=changed_lines_old,
                changed_lines_new=changed_lines_new,
                old_line_relation=old_line_relation,
            )
        elif not is_file_supported(
            new_entry.path.decode(), self.config["service"]["lang_suffix"]
        ):
            pass
        else:
            raise Exception(
                "ChangedFuncExtractor.parse error: change type is not support, should be add, modify or delete!"
            )
        return changed_methods
