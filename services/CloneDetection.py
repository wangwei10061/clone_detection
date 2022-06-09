# aim: this is used to implement the NIL clone detection method based on elasticsearch
# date: 2022-05-30
# author: zhangxunhui

import json

from ESUtils import ESUtils


class CloneDetection(object):
    def __init__(self, methods: list, config):
        self.methods = methods
        self.config = config
        self.es_utils = ESUtils(config=self.config)

    def locationPhase(self):
        """NIL location phase.
        1. use Elasticsearch to query the related
        """
        self.es_utils
        pass

    def filterPhase(self):
        pass

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
        return result


if __name__ == "__main__":
    print("finish")
