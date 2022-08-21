import os
import re
import shutil
import subprocess

from dulwich.objects import Commit
from models.MethodInfo import MethodInfo
from models.RepoInfo import RepoInfo

from services.utils import convert_time2utc, extract_n_grams, is_file_supported


class FuncExtractor:
    def __init__(
        self,
        repoInfo: RepoInfo,
        commit: Commit,
        filepath: str,
        content: str,
        config: dict,
        object_sha: str,
    ):
        self.repoInfo = repoInfo
        self.commit = commit
        self.commit_sha = self.commit.id.decode()
        self.filepath = filepath
        self.content = content
        self.config = config
        self.object_sha = object_sha
        self.methods = []  # used to store the methods in the file
        self.line_method_dict = (
            {}
        )  # the dictionary for line number and method relationship, key is line number; value is self.methods' index
        self.tokens = None

    def nilExtractFunctionsForFile(self):
        p = subprocess.Popen(
            [
                "java",
                "-jar",
                os.path.join(
                    self.config["nil"]["basepath"],
                    self.config["nil"]["rel_func_extractor_path"],
                ),
                "-rp",
                self.repoInfo.repo_path,
                "-os",
                self.object_sha,
                "-mit",
                str(self.config["service"]["mit"]),
                "-mil",
                str(self.config["service"]["mil"]),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output = p.stdout.read().decode("utf-8", errors="replace")
        _ = p.wait()
        lines = output.splitlines()
        method_num = int(lines[-1])
        if method_num > 0:
            for i in range(1, method_num + 1):
                method_line = lines[len(lines) - 1 - i]
                position, content = method_line.split(";")
                _, start_line, end_line = position.split(",")
                tokens = content.split(",")
                self.formMethodInfo(
                    start_line=int(start_line),
                    end_line=int(end_line),
                    tokens=tokens,
                )

    def formMethodInfo(self, start_line: int, end_line: int, tokens: list):
        # extract code_ngrams and gram_num and code
        code_ngrams = extract_n_grams(
            tokens=tokens,
            ngramSize=self.config["service"]["ngram"],
        )
        code_ngrams = list(set(code_ngrams))
        gram_num = len(code_ngrams)
        code = " ".join(tokens)
        self.methods.append(
            MethodInfo(
                repo_id=self.repoInfo.repo_id,
                filepath=self.filepath,
                start=start_line,
                end=end_line,
                tokens=tokens,
                code_ngrams=code_ngrams,
                gram_num=gram_num,
                code=code,
                ownername=self.repoInfo.ownername,
                reponame=self.repoInfo.reponame,
                commit_sha=self.commit_sha,
                created_at=convert_time2utc(
                    self.commit.author_time, self.commit.author_timezone
                ),
            )
        )
        for i in range(start_line, end_line + 1):
            self.line_method_dict[i] = len(self.methods) - 1

    def parse_file(self):
        """
        parse the file and extract methods & tokenize the methods
        return:
            - List of dict {filepath, start, end, tokens}
        """
        if is_file_supported(
            self.filepath.decode(), self.config["service"]["lang_suffix"]
        ):
            if self.filepath.endswith(b".java"):
                self.nilExtractFunctionsForFile()
        else:
            pass  # Currently do not support other programming languages
        return self.methods, self.line_method_dict
