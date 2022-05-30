# aim: this is used to implement the NIL clone detection method based on elasticsearch
# date: 2022-05-30
# author: zhangxunhui


class CloneDetection(object):
    def __init__(self, methods: list, config):
        self.methods = methods
        self.config = config

    def locationPhase(self):
        """NIL location phase.
        1.
        """
        pass

    def filterPhase(self):
        pass

    def verificationPhase(self):
        pass

    def run(self):
        for method in self.methods:
            self.locationPhase(method)


if __name__ == "__main__":
    print("finish")
