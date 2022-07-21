import os
import re
import subprocess

from dulwich.objects import Commit
from models.MethodInfo import MethodInfo
from models.RepoInfo import RepoInfo

from services.utils import convert_time2utc, is_file_supported


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
        self.temp_folder = "services/parser/txl/temp"
        self.temp_filepath = os.path.join(self.temp_folder, self.object_sha)

    def createTempFile(self) -> str:
        if not os.path.exists(self.temp_folder):
            os.makedirs(self.temp_folder)
        with open(self.temp_filepath, "w") as f:
            f.write(self.content.decode())

    def deleteTempFile(self):
        os.remove(self.temp_filepath)

    def txlExtractFunctionsForFile(self, filePath: str):
        # firstly create a temp file
        self.createTempFile()
        p = subprocess.Popen(
            [
                os.path.join(
                    self.config["txl"]["basepath"],
                    self.config["txl"]["relbinpath"],
                ),
                self.temp_filepath,
                os.path.join(
                    self.config["txl"]["basepath"],
                    self.config["txl"]["relextractorpath"],
                ),
                "-q",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output = p.stdout.read().decode("utf-8", errors="replace")
        _ = p.wait()
        # after analysis, delete the temp file
        self.deleteTempFile()
        return output

    def formMethodInfo(self, start_line: int, end_line: int, tokens: list):
        if len(tokens) >= self.config["service"]["mit"] and (
            end_line - start_line + 1 >= self.config["service"]["mil"]
        ):
            self.methods.append(
                MethodInfo(
                    repo_id=self.repoInfo.repo_id,
                    ownername=self.repoInfo.ownername,
                    reponame=self.repoInfo.reponame,
                    commit_sha=self.commit_sha,
                    created_at=convert_time2utc(
                        self.commit.author_time, self.commit.author_timezone
                    ),
                    filepath=self.filepath,
                    start=start_line,
                    end=end_line,
                    tokens=tokens,
                )
            )
            for i in range(start_line, end_line + 1):
                self.line_method_dict[i] = len(self.methods) - 1

    def extractFunInfo(self, output, filepath):
        result = []  # store hash {"filepath", "start", "end", "code"}
        startlineno = -1
        endlineno = -1
        snippetLines = []
        lines = output.splitlines()
        for line in lines:
            if re.match(r"^\d+ ", line):
                tmp = line.split(" ")
                startlineno = int(tmp[0])
                line = " ".join(tmp[1:])
                snippetLines.append(line)
            elif re.match(r"\d+\}$", line):
                endlineno = int(line.split("}")[0])
                line = "}"
                snippetLines.append(line)
                result.append(
                    {
                        "filepath": filepath,
                        "start": startlineno,
                        "end": endlineno,
                        "code": "\n".join(snippetLines),
                    }
                )
                startlineno = -1
                endlineno = -1
                snippetLines = []
            elif re.match(r"^(\d+)\} (\d+) ", line):
                m = re.match(r"^(\d+)\} (\d+) ", line)
                endlineno = int(m.group(1))
                snippetLines.append("}")
                result.append(
                    {
                        "filepath": filepath,
                        "start": startlineno,
                        "end": endlineno,
                        "code": "\n".join(snippetLines),
                    }
                )
                startlineno = int(m.group(2))
                endlineno = -1
                snippetLines = []
                line = " ".join(line.split(" ")[2:])
                snippetLines.append(line)
            else:
                snippetLines.append(line)
        for item in result:
            self.formMethodInfo(
                start_line=item["start"],
                end_line=item["end"],
                tokens=item["code"].split(),
            )

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
                self.extractFunInfo(
                    self.txlExtractFunctionsForFile(self.filepath),
                    self.filepath.decode(),
                )
        else:
            pass  # Currently do not support other programming languages
        return self.methods, self.line_method_dict
