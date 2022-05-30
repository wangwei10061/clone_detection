# aim: The utilities of elastic search operations
# author: zhangxunhui
# date: 2022-05-27

from typing import List

from elasticsearch import Elasticsearch, helpers
from Method import Method


class ESUtils(object):
    def __init__(self, config):
        self.config = config
        self.urls = self.config["elasticsearch"]["urls"]
        self.client = self.connect()

    def connect(self):
        client = Elasticsearch(self.urls)
        return client

    def insert_es_bulk(self, bulk):
        helpers.bulk(self.client, bulk)

    def insert_es_item(self, item, index_name: str):
        self.client.index(index=index_name, body=item)

    def get_handled_commits(self, repo_id: int, index_name: str):
        handled_commits = set()
        body = {"query": {"term": {"repo_id": repo_id}}}
        scroll = "2m"
        size = 50
        if not self.client.indices.exists(index=index_name):
            return handled_commits  # index has not been created yet
        else:
            page = self.client.search(
                index=index_name, body=body, scroll=scroll, size=size
            )
            hits = page["hits"]["hits"]
            scroll_id = page.body["_scroll_id"]
            while len(hits):
                commit_shas = [hit["_source"]["commit_sha"] for hit in hits]
                handled_commits = handled_commits.union(commit_shas)
                page = self.client.scroll(scroll_id=scroll_id, scroll=scroll)
                scroll_id = page.body["_scroll_id"]
                hits = page["hits"]["hits"]
            return list(handled_commits)

    def extract_n_grams(self, tokens: list, n=5):
        ngrams = []
        for i in range(0, len(tokens) - n + 1):
            ngram = (" ".join(tokens[i : i + n])).lower()
            ngrams.append(ngram)
        return ngrams

    def extract_es_infos(self, changed_methods: List[Method]):
        es_data_bulk = []  # used to store the extracted change
        # for changed methods, extract N-Gram list
        for changed_method in changed_methods:
            ngrams = self.extract_n_grams(changed_method.tokens)
            # update the inverted index of elastic search
            for ngram in ngrams:
                es_data = {
                    "_index": self.config["elasticsearch"]["index_ngram"],
                    "doc_as_upsert": True,
                    "doc": {
                        "ownername": changed_method.ownername,
                        "reponame": changed_method.reponame,
                        "commit_sha": changed_method.commit_sha,
                        "filepath": changed_method.filepath.decode(),
                        "start_line": changed_method.start,
                        "end_line": changed_method.end,
                        "gram": ngram,
                    },
                }
                es_data_bulk.append(es_data)
        return es_data_bulk
