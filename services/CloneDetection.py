# aim: this is used to implement the NIL clone detection method based on elasticsearch
# date: 2022-05-30
# author: zhangxunhui

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
        for method in self.methods:
            result = self.es_utils.search_method(
                search_string=" ".join(method.tokens)
            )
            # result = self.es_utils.search_method(search_string="> invoker invocation invocation rpccontext geturl service monitorservice method method monitorservice > last = invoker list")
            print(result)


if __name__ == "__main__":
    print("finish")
