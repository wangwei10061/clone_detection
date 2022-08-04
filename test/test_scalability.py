# aim: explain our limitation of scalability
# author: zhangxunhui
# date: 2022-07-28

import os
import shutil
import subprocess
import sys
import time
import tracemalloc
from typing import List

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)
sys.path.append(os.path.join(parentdir, "services"))
from elasticsearch import helpers

from services.ESUtils import ESUtils
from services.LCS import LCS
from services.utils import extract_n_grams, read_config

service_config_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    "services/config.yml",
)
service_config = read_config(service_config_path)

FakeTargetDir = "test/test_scalability_middle_results/fake_repos"


def download_target_project():
    target_dir = "test/test_scalability_middle_results"
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
        shutil.rmtree(
            os.path.join(target_dir, "Ant1.10.1", ".git"), ignore_errors=True
        )
    print("Finish downloading target project!")


def copy_fake_repos(repo_num):
    # 多退少补
    if not os.path.exists(FakeTargetDir):
        os.makedirs(FakeTargetDir)

    # calculate the number of already existed repos
    already_num = len(os.listdir(FakeTargetDir))

    if repo_num > already_num:
        for i in range(already_num + 1, repo_num + 1):
            shutil.copytree(
                "test/test_scalability_middle_results/Ant1.10.1",
                os.path.join(FakeTargetDir, str(i)),
            )
    elif already_num > repo_num:
        for i in range(already_num, repo_num, -1):
            shutil.rmtree(os.path.join(FakeTargetDir, str(i)))
    print("Finish copying fake repositories!")


def refresh_indices():
    # init the es connector, and refresh the index
    es_utils = ESUtils(config=service_config)

    n_gram_index_name = "test_performance_n_grams"
    es_utils.delete_index(n_gram_index_name)
    es_utils.client.indices.create(
        index=n_gram_index_name,
        settings={
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "similarity": {"default": {"type": "boolean"}},
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
                "code_ngrams": {"type": "keyword"},
                "code": {"type": "text"},
                "gram_num": {"type": "integer"},
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

        if "code_ngrams" in kwargs:
            self.code_ngrams = kwargs["code_ngrams"]
        else:
            self.code_ngrams = None

        if "code" in kwargs:
            self.code = kwargs["code"]
        else:
            self.code = None

        if "ngrams" in kwargs:
            self.ngrams = kwargs["ngrams"]
        else:
            self.ngrams = None

        if "gram_num" in kwargs:
            self.gram_num = kwargs["gram_num"]
        else:
            self.gram_num = None


class FuncExtractor(object):
    def __init__(
        self,
        folder: str,
    ):
        self.folder = folder
        self.methods = []  # used to store the methods in the file
        self.tokens = None

    def nilExtractFunctionsForFolder(self):
        p = subprocess.Popen(
            "java -jar test/NIL-func-extractor-file.jar -f {folder} -mit 50 -mil 6".format(
                folder=self.folder
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
                filepath, start_line, end_line = position.split(",")
                tokens = content.split(",")
                self.formMethodInfo(
                    filepath=filepath,
                    start_line=int(start_line),
                    end_line=int(end_line),
                    tokens=tokens,
                )

    def formMethodInfo(
        self, filepath: str, start_line: int, end_line: int, tokens: list
    ):
        # extract code_ngrams and gram_num and code
        code_ngrams = extract_n_grams(
            tokens=tokens,
            ngramSize=5,
        )
        code_ngrams = list(set(code_ngrams))
        gram_num = len(code_ngrams)
        code = " ".join(tokens)
        self.methods.append(
            MethodInfo(
                filepath=filepath,
                start=start_line,
                end=end_line,
                tokens=tokens,
                code_ngrams=code_ngrams,
                gram_num=gram_num,
                code=code,
            )
        )

    def parse(self):
        self.nilExtractFunctionsForFolder()
        return self.methods


class CloneDetection(object):
    def __init__(self, method: MethodInfo, es_utils: ESUtils):
        self.method = method
        self.es_utils = es_utils

    def filterPhase(self, candidates: List[dict]):
        """NIL filter phase.
        common distinct n-grams * 100 / min(distinct n-grams) >= 10%
        """
        if self.method.ngrams is None:
            self.method.ngrams = extract_n_grams(
                tokens=self.method.tokens,
                ngramSize=5,
            )

        def _filter(candidate):
            candidate_ngrams = extract_n_grams(
                tokens=candidate["code_ngrams"].split(" "),
                ngramSize=5,
            )
            minV = min(
                len(set(self.method.ngrams)), len(set(candidate_ngrams))
            )
            return (
                len(set(candidate_ngrams) & set(self.method.ngrams))
                * 100
                / minV
                >= 10
            )

        return list(filter(_filter, candidates))

    def verificationPhase(self, candidates: List[dict]):
        """NIL verify phase.
        lcs.calcLength(tokenSequence1, tokenSequence2) * 100 / min >= 70%
        """
        X = self.method.tokens
        result = []
        for candidate in candidates:
            Y = candidate["code"].split(" ")
            minV = min(len(X), len(Y))
            sim = LCS().lcs(X, Y) * 100 / minV
            if sim >= 70:
                candidate["similarity"] = sim
                result.append(candidate)
        return result

    def run(self):

        # 1. location phase
        search_results = []
        query = {
            "query": {
                "terms_set": {
                    "code_ngrams": {
                        "terms": self.method.code_ngrams,
                        "minimum_should_match_script": {
                            "source": "Math.ceil(Math.min(params.num_terms, doc['gram_num'].value) * 0.1)"
                        },
                    }
                }
            }
        }
        search_results = helpers.scan(
            client=self.es_utils.client,
            query=query,
            scroll="1m",
            index="test_performance_n_grams",
        )

        candidates = []
        for search_result in search_results:
            candidates.append(
                {
                    "filepath": search_result["_source"]["filepath"],
                    "start": search_result["_source"]["start_line"],
                    "end": search_result["_source"]["end_line"],
                    "code_ngrams": search_result["_source"]["code_ngrams"],
                    "code": search_result["_source"]["code"],
                    "gram_num": search_result["_source"]["gram_num"],
                }
            )

        # 3. verify phase
        candidates = self.verificationPhase(candidates=candidates)
        return candidates


class HandleFile(object):
    def __init__(
        self, filepath: str, methods: List[MethodInfo], es_utils: ESUtils
    ):
        self.filepath = filepath
        self.methods = methods
        self.es_utils = es_utils

    def record_clones(self, method: MethodInfo, clones: List[dict]):
        with open(
            "test/test_scalability_middle_results/LSICCDS_clone_pairs", "a"
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
        # print(
        #     "[Info]: Handling file {filepath}".format(filepath=self.filepath)
        # )

        """Do clone detection for each method."""
        for method in self.methods:
            clones = CloneDetection(
                method=method, es_utils=self.es_utils
            ).run()
            # record the results
            self.record_clones(method=method, clones=clones)

            es_data = {
                "filepath": method.filepath,
                "start_line": method.start,
                "end_line": method.end,
                "code_ngrams": method.code_ngrams,
                "code": method.code,
                "gram_num": method.gram_num,
            }
            self.es_utils.insert_es_item(
                item=es_data,
                index_name="test_performance_n_grams",
            )

        """Finish handling this file, insert into the handled_files index in es."""
        es_data = {"filepath": self.filepath}
        self.es_utils.insert_es_item(
            item=es_data,
            index_name="test_performance_handled_files",
        )


class LSICCDSScalabilityDetector(object):
    def __init__(self, repo_num) -> None:
        self.es_utils = ESUtils(config=service_config)
        self.repo_num = repo_num

    def is_file_handled(self, filepath: str):
        query = {"term": {"filepath": filepath}}
        result = self.es_utils.client.search(
            index="test_performance_handled_files", query=query
        )
        hits = result["hits"]["hits"]
        return len(hits) > 0

    def run(self):
        # find all the unhandled methods
        methods = FuncExtractor(
            folder=os.path.join(FakeTargetDir, str(self.repo_num))
        ).parse()

        fm_dict = form_file_method_dict(methods=methods)
        for filepath in list(fm_dict.keys()):
            # check whether file have already handled
            if not self.is_file_handled(filepath=filepath):
                HandleFile(
                    filepath=filepath,
                    methods=fm_dict[filepath],
                    es_utils=self.es_utils,
                ).run()
                return True


def insert_fake_records(es_utils: ESUtils, repo_num: int):
    """Need to handle {repo_num} fake repositories. So we need to insert {repo_num-1} fake records."""
    # Extract fake info from 1 project
    repo1_path = os.path.join(FakeTargetDir, "1")
    methods_repo1 = []
    methods = FuncExtractor(folder=repo1_path).parse()
    for method in methods:
        method.filepath = os.path.relpath(
            method.filepath,
            repo1_path,
        )
    methods_repo1.extend(methods)

    for method in methods_repo1:
        actions = []
        for i in range(1, repo_num):
            action = {
                "_op_type": "create",
                "_index": "test_performance_n_grams",
                "filepath": os.path.join(
                    FakeTargetDir,
                    str(i),
                    method.filepath,
                ),
                "start_line": method.start,
                "end_line": method.end,
                "code_ngrams": method.code_ngrams,
                "code": method.code,
                "gram_num": method.gram_num,
            }
            actions.append(action)
        es_utils.insert_es_bulk(actions)

    fm_dict = form_file_method_dict(methods=methods_repo1)
    list_of_files_repo1 = list(fm_dict.keys())

    for filepath in list_of_files_repo1:
        actions = []
        for i in range(1, repo_num):
            action = {
                "_op_type": "create",
                "_index": "test_performance_handled_files",
                "filepath": os.path.join(
                    FakeTargetDir,
                    str(i),
                    filepath,
                ),
            }
            actions.append(action)
        es_utils.insert_es_bulk(actions)


def form_file_method_dict(methods: List[MethodInfo]):
    result = {}  # key: filepath, value: [MethodInfo]
    for method in methods:
        result.setdefault(method.filepath, [])
        result[method.filepath].append(method)
    return result


def cal_loc():
    """
    270028 loc for one Ant1.10.1 repository
    """
    folder = "test/test_scalability_middle_results/Ant1.10.1"
    result = 0
    for root, directories, files in os.walk(folder):
        for name in files:
            if name.endswith(".java"):
                print(os.path.join(root, name))
                count = len(open(os.path.join(root, name), "r").readlines())
                result += count
    return result


if __name__ == "__main__":

    # cal_loc()

    # download the repository
    download_target_project()

    repo_nums = [
        5000
    ]  # 5000跑不了 Caused by: java.lang.OutOfMemoryError: Java heap space
    for repo_num in repo_nums:
        print(
            "Repo num: {repo_num}, loc: {loc}".format(
                repo_num=repo_num, loc=str(270028 * repo_num)
            )
        )
        # copy the test repositories into directory "test/test_scalability_middle_results/fake_repos"
        copy_fake_repos(repo_num=repo_num)

        # delete and re-create the indices
        # refresh_indices()

        # insert fake records into elasticsearch
        insert_fake_records(
            es_utils=ESUtils(config=service_config), repo_num=repo_num
        )

        # nohup java -Xmx32768m -jar test/NIL-func-extractor-file.jar -f "test/test_scalability_middle_results/fake_repos" -mit 50 -mil 6 -t 8 > test/test_scalability_nil.log 2>&1 &

        # run LSICCDSScalabilityDetector
        print(LSICCDSScalabilityDetector(repo_num).run())

        print("finish")
