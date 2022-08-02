# aim: this is used to implement the NIL clone detection method based on elasticsearch
# date: 2022-05-30
# author: zhangxunhui

import json
from typing import List

from ESUtils import ESUtils
from LCS import LCS
from models.MethodInfo import MethodInfo
from utils import extract_n_grams


class CloneDetection(object):
    def __init__(self, methods: list, config):
        self.methods = methods
        self.config = config
        self.es_utils = ESUtils(config=self.config)

    def filterPhase(self, method: MethodInfo, candidates: List[dict]):
        """NIL filter phase.
        common distinct n-grams * 100 / min(distinct n-grams) >= 10%
        """
        if method.ngrams is None:
            method.ngrams = extract_n_grams(
                tokens=method.tokens,
                ngramSize=self.config["service"]["ngram"],
            )

        def _filter(candidate):
            candidate_ngrams = extract_n_grams(
                tokens=candidate["code"].split(" "),
                ngramSize=self.config["service"]["ngram"],
            )
            minV = min(len(set(method.ngrams)), len(set(candidate_ngrams)))
            return (
                len(set(candidate_ngrams) & set(method.ngrams)) * 100 / minV
                >= self.config["service"]["filter_threshold"]
            )
            # return (
            #     len(set(candidate_ngrams) & set(method.ngrams)) * 100 / minV
            #     >= 1  # only for test
            # )

        return list(filter(_filter, candidates))

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

            # 1. location phase
            search_results = self.es_utils.search_method_filter(
                search_string=" ".join(method.tokens),
                repo_id=method.repo_id,
                filepath=method.filepath.decode(),
            )
            # search_result = self.es_utils.search_method(search_string="> invoker invocation invocation rpccontext geturl service monitorservice method method monitorservice > last = invoker list")

            for search_result in search_results:
                result.setdefault(method_str, [])
                result[method_str].append(
                    {
                        "commit_sha": search_result["_source"]["commit_sha"],
                        "created_at": search_result["_source"]["created_at"],
                        "repo_id": search_result["_source"]["repo_id"],
                        "filepath": search_result["_source"]["filepath"],
                        "start": search_result["_source"]["start_line"],
                        "end": search_result["_source"]["end_line"],
                        "code_ngrams": search_result["_source"]["code_ngrams"],
                        "code": search_result["_source"]["code"],
                    }
                )

            # 2. filter phase
            result[method_str] = self.filterPhase(
                method=method, candidates=result[method_str]
            )

            # 3. verify phase
            result[method_str] = self.verificationPhase(
                method=method, candidates=result[method_str]
            )

            # 4. sort the result and get the oldest one
            def _sort_key(ele):
                return ele["created_at"]

            result[method_str].sort(key=_sort_key)

            # 5. keep the first one
            if len(result[method_str]) > 0:
                result[method_str] = result[method_str][:1]
            else:
                del result[method_str]

        return result


if __name__ == "__main__":
    print("finish")
