# aim: The utilities of elastic search operations
# author: zhangxunhui
# date: 2022-05-27

import json

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

    def get_handled_commits(self, repo_id):
        handled_commits = set()
        body = {"query": {"term": {"repo_id": repo_id}}}
        scroll = "2m"
        size = 50
        page = self.client.search(
            index="handled_commits", body=body, scroll=scroll, size=size
        )
        hits = page["hits"]["hits"]
        scroll_id = page.body["_scroll_id"]
        while len(hits):
            commit_shas = [hits[0]["_source"]["commit_sha"] for hit in hits]
            handled_commits = handled_commits.union(commit_shas)
            page = self.client.scroll(scroll_id=scroll_id, scroll=scroll)
            scroll_id = page.body["_scroll_id"]
            hits = page["hits"]["hits"]
        return list(handled_commits)
