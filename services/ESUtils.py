# aim: The utilities of elastic search operations
# author: zhangxunhui
# date: 2022-05-27

from elasticsearch import Elasticsearch, helpers


class ESUtils(object):
    def __init__(self, urls: list):
        if type(urls) != list:
            raise Exception("ESUtils Error: urls configuration wrong!")
        self.urls = urls
        self.client = self.connect()

    def connect(self):
        client = Elasticsearch(self.urls)
        return client

    def insert_es_bulk(self, bulk):
        helpers.bulk(self.client, bulk)

    def insert_es_item(self, item):
        self.client.index(index="handled_commits", body=item)
