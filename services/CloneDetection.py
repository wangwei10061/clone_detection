# aim: this is used to implement the NIL clone detection method based on elasticsearch
# date: 2022-05-30
# author: zhangxunhui

import json
from typing import List

from ESUtils import ESUtils
from LCS import LCS
from models.MethodInfo import MethodInfo


class CloneDetection(object):
    def __init__(self, methods: list, config):
        self.methods = methods
        self.config = config
        self.es_utils = ESUtils(config=self.config)

    def verificationPhase(self, method: MethodInfo, candidates: List[dict]):
        """NIL verify phase.
        lcs.calcLength(tokenSequence1, tokenSequence2) * 100 / min >= 70%
        """
        X = method.tokens
        result = []
        for candidate in candidates:
            Y = candidate["code"].split(" ")
            minV = min(len(X), len(Y))
            sim = LCS().lcs(X, Y) * 100 / minV
            if sim >= self.config["service"]["verify_threshold"]:
                # if sim >= 1:  # only for test
                candidate["similarity"] = sim
                result.append(candidate)
        return result

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

            # 1. location and filtration phase
            result.setdefault(method_str, [])
            search_results = self.es_utils.search_method_filter(method=method)

            for search_result in search_results:
                result[method_str].append(
                    {
                        "commit_sha": search_result["_source"]["commit_sha"],
                        "created_at": search_result["_source"]["created_at"],
                        "repo_id": search_result["_source"]["repo_id"],
                        "filepath": search_result["_source"]["filepath"],
                        "start_line": search_result["_source"]["start_line"],
                        "end_line": search_result["_source"]["end_line"],
                        "code_ngrams": search_result["_source"]["code_ngrams"],
                        "code": search_result["_source"]["code"],
                    }
                )

            # 2. verify phase
            result[method_str] = self.verificationPhase(
                method=method, candidates=result[method_str]
            )

            # 3. sort the result and get the oldest one
            def _sort_key(ele):
                return ele["created_at"]

            result[method_str].sort(key=_sort_key)

            # 4. keep the first one
            if len(result[method_str]) > 0:
                result[method_str] = result[method_str][:1]
            else:
                del result[method_str]

        return result


if __name__ == "__main__":
    print("finish")
