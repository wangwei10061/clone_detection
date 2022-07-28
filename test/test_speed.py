# aim: verify that our running speed is faster than NIL in incremental situation
# author: zhangxunhui
# date: 2022-07-28

"""
Here we use Ant 1.10.1 system mentioned in NIL and copy it X times for clone detection.
"""

import json
import os
import shutil
import subprocess
import sys
from typing import List

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)
sys.path.append(os.path.join(parentdir, "services"))
from services.ESUtils import ESUtils
from services.LCS import LCS
from services.models.RepoInfo import RepoInfo
from services.utils import extract_n_grams, read_config

service_config_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    "services/config.yml",
)
service_config = read_config(service_config_path)

REPONUM = 1  # define the number of fake repositories we want to detect


def download_target_project():
    target_dir = "test/test_speed_middle_results"
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


def copy_fake_repos(repo_num):
    target_dir = "test/test_speed_middle_results/fake_repos"
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir, ignore_errors=True)
    os.makedirs(target_dir)

    for i in range(1, repo_num + 1):
        shutil.copytree(
            "test/test_speed_middle_results/Ant1.10.1",
            os.path.join(target_dir, str(i)),
        )
    print("Finish copying fake repositories!")


def refresh_indices():
    # init the es connector, and refresh the index
    es_utils = ESUtils(config=service_config)

    n_gram_index_name = "test_performance_n_grams"
    es_utils.delete_index(n_gram_index_name)
    es_utils.client.indices.create(
        index=n_gram_index_name,
        settings={
            "analysis": {
                "filter": {
                    "my_shingle_filter": {
                        "type": "shingle",
                        "min_shingle_size": 5,
                        "max_shingle_size": 5,
                        "output_unigrams": "false",
                    }
                },
                "analyzer": {
                    "shingle_analyzer": {
                        "filter": [
                            "lowercase",
                            "my_shingle_filter",
                        ],
                        "type": "custom",
                        "tokenizer": "whitespace",
                    }
                },
            },
        },
        mappings={
            "properties": {
                "filepath": {"type": "keyword"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
                "code_ngrams": {
                    "type": "text",
                    "analyzer": "shingle_analyzer",
                    "search_analyzer": "shingle_analyzer",
                },
            }
        },
    )

    handled_file_index_name = "test_performance_handled_files"
    es_utils.delete_index(handled_file_index_name)
    es_utils.client.indices.create(
        index=handled_file_index_name,
        mappings={
            "properties": {
                "filepath": {"type": "keyword"},
            }
        },
    )


class MethodInfo(object):
    def __init__(
        self,
        **kwargs,
    ):

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


class FuncExtractor(object):
    def __init__(
        self,
        filepath: str,
    ):
        self.filepath = filepath
        self.methods = []  # used to store the methods in the file
        self.tokens = None

    def nilExtractFunctionsForFile(self):
        p = subprocess.Popen(
            "java -jar test/NIL-func-extractor-file.jar -fp {filepath} -mit 50 -mil 6".format(
                filepath=self.filepath
            ),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output = p.stdout.read().decode("utf-8", errors="replace")
        _ = p.wait()
        lines = output.split("\n")
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
        self.methods.append(
            MethodInfo(
                filepath=self.filepath,
                start=start_line,
                end=end_line,
                tokens=tokens,
            )
        )

    def parse_file(self):
        self.nilExtractFunctionsForFile()
        return self.methods


class CloneDetection(object):
    def __init__(self, method: MethodInfo, es_utils: ESUtils):
        self.method = method
        self.es_utils = es_utils

    def filterPhase(self, method: MethodInfo, candidates: List[dict]):
        """NIL filter phase.
        common distinct n-grams * 100 / min(distinct n-grams) >= 10%
        """
        if method.ngrams is None:
            method.ngrams = extract_n_grams(
                tokens=" ".join(method.tokens).split(" "),
                ngramSize=5,
            )

        def _filter(candidate):
            candidate_ngrams = extract_n_grams(
                tokens=candidate["code_ngrams"].split(" "),
                ngramSize=5,
            )
            minV = min(len(set(method.ngrams)), len(set(candidate_ngrams)))
            return (
                len(set(candidate_ngrams) & set(method.ngrams)) * 100 / minV
                >= 10
            )

        return list(filter(_filter, candidates))

    def verificationPhase(self, method: MethodInfo, candidates: List[dict]):
        """NIL verify phase.
        lcs.calcLength(tokenSequence1, tokenSequence2) * 100 / min >= 70%
        """
        X = " ".join(method.tokens).split(" ")
        result = []
        for candidate in candidates:
            Y = candidate["code_ngrams"].split(" ")
            minV = min(len(X), len(Y))
            sim = LCS().lcs(X, Y) * 100 / minV
            if sim >= 70:
                candidate["similarity"] = sim
                result.append(candidate)
        return result

    def run(self):

        # 1. location phase
        query = {
            "bool": {
                "must": {
                    "match": {
                        "code_ngrams": {"query": " ".join(self.method.tokens)}
                    }
                },
            }
        }
        data = self.es_utils.client.search(
            index="test_performance_n_grams", query=query
        )
        search_results = data.body["hits"]["hits"]

        candidates = []
        for search_result in search_results:
            candidates.append(
                {
                    "filepath": search_result["_source"]["filepath"],
                    "start": search_result["_source"]["start_line"],
                    "end": search_result["_source"]["end_line"],
                    "code_ngrams": search_result["_source"]["code_ngrams"],
                }
            )

        # 2. filter phase
        candidates = self.filterPhase(
            method=self.method, candidates=candidates
        )

        # 3. verify phase
        candidates = self.verificationPhase(
            method=self.method, candidates=candidates
        )

        return candidates


class HandleFile(object):
    def __init__(self, filepath: str, es_utils: ESUtils):
        self.filepath = filepath
        self.es_utils = es_utils

    def record_clones(self, method: MethodInfo, clones: List[dict]):
        with open(
            "test/test_speed_middle_results/LSICCDS_clone_pairs", "a"
        ) as f:
            for clone in clones:
                f.write(
                    method.filepath
                    + ","
                    + str(method.start)
                    + ","
                    + str(method.end)
                    + ";"
                    + clone["filepath"]
                    + ","
                    + str(clone["start"])
                    + ","
                    + str(clone["end"])
                    + "\n"
                )

    def run(self):
        print(
            "[Info]: Handling file {filepath}".format(filepath=self.filepath)
        )

        methods = FuncExtractor(filepath=self.filepath).parse_file()

        """Do clone detection for each method."""
        for method in methods:
            clones = CloneDetection(
                method=method, es_utils=self.es_utils
            ).run()
            # record the results
            self.record_clones(method=method, clones=clones)

        actions = []  # used to store the method infos
        # for changed methods, extract N-Gram list
        for method in methods:
            code = " ".join(method.tokens)
            # update the inverted index of elastic search
            action = {
                "_op_type": "create",
                "_index": "test_performance_n_grams",
                "filepath": method.filepath,
                "start_line": method.start,
                "end_line": method.end,
                "code_ngrams": code,
            }
            actions.append(action)
        self.es_utils.insert_es_bulk(actions)

        """Finish handling this file, insert into the handled_files index in es."""
        es_data = {"filepath": self.filepath}
        self.es_utils.insert_es_item(
            item=es_data,
            index_name="test_performance_handled_files",
        )


class LSICCDSSpeedDetector:
    def __init__(self) -> None:
        self.es_utils = ESUtils(config=service_config)

    def is_file_handled(self, filepath: str):
        query = {"term": {"filepath": filepath}}
        scroll = "2m"
        size = 50
        page = self.es_utils.client.search(
            index="test_performance_handled_files",
            query=query,
            scroll=scroll,
            size=size,
        )
        hits = page["hits"]["hits"]
        return len(hits) > 0

    def run(self):
        # find all the java files
        list_of_files = []
        for root, directories, files in os.walk(
            "test/test_speed_middle_results"
        ):
            for file in files:
                if file.endswith(".java"):
                    list_of_files.append(os.path.join(root, file))
        for filepath in list_of_files:
            # check whether file have already handled
            if not self.is_file_handled(filepath=filepath):
                HandleFile(
                    filepath=filepath,
                    es_utils=self.es_utils,
                ).run()


class NILSpeedDetector:
    def __init__(self) -> None:
        print("pause")

    def run(self):
        print("pause")


if __name__ == "__main__":

    # download the repository
    download_target_project()

    # delete and re-create the indices
    refresh_indices()

    # delete the clone_pairs file
    if os.path.exists("test/test_speed_middle_results/LSICCDS_clone_pairs"):
        os.remove("test/test_speed_middle_results/LSICCDS_clone_pairs")

    for repo_num in range(1, REPONUM + 1):

        # copy the test repositories into directory "test/test_speed_middle_results/fake_repos"
        copy_fake_repos(repo_num=repo_num)

        # run LSICCDSSpeedDetector
        LSICCDS_detector = LSICCDSSpeedDetector()
        LSICCDS_detector.run()

        # run NILSpeedDetector
        NIL_detector = NILSpeedDetector()
        NIL_detector.run()

    print("finish")
