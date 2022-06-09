# aim: this is used to implement the NIL clone detection method based on elasticsearch
# date: 2022-05-30
# author: zhangxunhui

import json
from typing import List

from ESUtils import ESUtils
from models.MethodInfo import MethodInfo


class CloneDetection(object):
    def __init__(self, methods: list, config):
        self.methods = methods
        self.config = config
        self.es_utils = ESUtils(config=self.config)

    def locationPhase(self):
        """NIL location phase.
        Use Elasticsearch's search engine instead
        """
        pass

    def filterPhase(self, method: MethodInfo, candidates: List[dict]):
        """NIL filter phase.
        common distinct n-grams * 100 / min(distinct n-grams) >= 10%
        """
        method_n_grams = {}
        for i in range(
            0, len(method.tokens) - self.config["service"]["ngram"] + 1
        ):
            ngram = (
                self.config["service"]["ngram_connector"].join(
                    method.tokens[i : i + self.config["service"]["ngram"]]
                )
            ).lower()
            method_n_grams.setdefault(ngram, 0)
            method_n_grams[ngram] += 1

        def _filter(candidate):
            # 转换为dict存储ngram
            print("pause")
            pass

        return filter(_filter, candidates)

    def verificationPhase(self):
        pass

    def run(self):
        result = (
            {}
        )  # key: MethodInfo, value: {commit_sha, repo_id, filepath, start, end}
        for method in self.methods:
            method_str = json.dumps(
                {
                    "filepath": method.filepath.decode(),
                    "start": method.start,
                    "end": method.end,
                }
            )

            # 1. location phase
            search_results = self.es_utils.search_method_filter(
                search_string=" ".join(method.tokens).lower(),
                repo_id=method.repo_id,
                filepath=method.filepath.decode(),
            )
            # search_result = self.es_utils.search_method(search_string="> invoker invocation invocation rpccontext geturl service monitorservice method method monitorservice > last = invoker list")

            for search_result in search_results:
                result.setdefault(method_str, [])
                result[method_str].append(
                    {
                        "commit_sha": search_result["_source"]["doc"][
                            "commit_sha"
                        ],
                        "repo_id": search_result["_source"]["doc"]["repo_id"],
                        "filepath": search_result["_source"]["doc"][
                            "filepath"
                        ],
                        "start": search_result["_source"]["doc"]["start_line"],
                        "end": search_result["_source"]["doc"]["end_line"],
                    }
                )

            # 2. filter phase
            self.filterPhase(method=method, candidates=search_results)
        return result


if __name__ == "__main__":
    print("finish")
