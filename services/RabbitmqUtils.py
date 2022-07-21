# aim: The utilities of rabbitmq operations
# author: zhangxunhui
# date: 2022-06-07

from typing import List

import pika


class RabbitmqUtils(object):
    def __init__(self, config: dict):
        self.config = config
        self.conn = self.connect()

    def connect(self):
        parameters = pika.ConnectionParameters(
            host=self.config["rabbitmq"]["host"],
            port=self.config["rabbitmq"]["port"],
            heartbeat=0,
        )
        connection = pika.BlockingConnection(parameters=parameters)
        return connection

    def close(self):
        self.conn.close()

    def sendMsgs(self, queueName, msgs):
        channel = self.conn.channel()
        channel.queue_declare(queue=queueName, durable=True)
        for msg in msgs:
            channel.basic_publish(
                exchange="",
                routing_key=queueName,
                body=msg.serialize(),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                ),
            )
        self.close()

    def purgeMQ(self, queueName):
        channel = self.conn.channel()
        channel.queue_purge(queue=queueName)
        self.close()

    def calRemainedTasks(self, queueName):
        channel = self.conn.channel()
        queue = channel.queue_declare(queue=queueName, durable=True)
        qSize = queue.method.message_count
        self.close()
        return qSize
