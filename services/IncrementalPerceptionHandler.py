# aim: The IncrementalPerception service handler for LSICCDS_server
# author: zhangxunhui
# date: 2022-06-08

import json
import threading

import IncrementalPerceptionAPI as apiClass
from models.CommitInfo import CommitInfo
from RabbitmqUtils import RabbitmqUtils


class IncrementalPerceptionHandler(threading.Thread):
    def __init__(self, name):
        threading.Thread.__init__(self)
        self.name = name
        self.rabbitmqUtils = RabbitmqUtils(apiClass.config)

    def run(self):
        print("[Info]: Start thread: " + self.name)

        conn = self.rabbitmqUtils.connect()
        channel = conn.channel()
        channel.queue_declare(queue=apiClass.QUEUENAME, durable=True)
        channel.basic_consume(
            queue=apiClass.QUEUENAME,
            on_message_callback=self.callback,
            auto_ack=True,
        )
        channel.start_consuming()  # this will block if there is no task remained in the queue

    def callback(self, ch, method, properties, body):
        task = json.loads(str(body, encoding="utf-8"))
        commitInfo = CommitInfo.dict2obj(task)
        print(commitInfo)


if __name__ == "__main__":

    THREADNUM = apiClass.config["incremental_service"]["THREADNUM"]
    QUEUENAME = "incremental_update_graph_task"

    threads = []
    for i in range(THREADNUM):
        t = IncrementalPerceptionHandler(name="Thread-" + str(i + 1))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
