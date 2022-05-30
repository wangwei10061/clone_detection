# aim: this is the object of a method
# date: 2022-05-30
# author: zhangxunhui


class Method(object):
    def __init__(self, filepath: bytes, start: int, end: int, tokens: list):
        self.filepath = filepath
        self.start = start
        self.end = end
        self.tokens = tokens
