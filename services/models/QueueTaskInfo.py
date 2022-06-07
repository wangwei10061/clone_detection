# aim: this is used to serialize objects into rabbitmq
# date: 2022-06-07
# author: zhangxunhui

import json


class QueueTaskInfo:

    type: str

    def __init__(self, type):
        self.type = type

    def serialize(self):
        return json.dumps(self.__dict__)
