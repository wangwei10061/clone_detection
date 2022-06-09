# aim: The utilities of elastic search operations
# author: zhangxunhui
# date: 2022-05-27

from typing import List

from elasticsearch import Elasticsearch, helpers
from models.MethodInfo import MethodInfo


class ESUtils(object):
    def __init__(self, config: dict):
        self.config = config
        self.urls = self.config["elasticsearch"]["urls"]
        self.client = self.connect()
        self.special_connector = " "

    def connect(self):
        client = Elasticsearch(self.urls)
        return client

    def is_index_exists(self, index_name: str):
        if self.client.indices.exists(index=index_name):
            return True
        else:
            return False

    def create_n_gram_index(self):
        if self.is_index_exists(
            index_name=self.config["elasticsearch"]["index_ngram"]
        ):
            return
        else:
            self.client.indices.create(
                index=self.config["elasticsearch"]["index_ngram"],
                body={
                    "settings": {
                        "analysis": {
                            "filter": {
                                "n_gram_filter": {
                                    "type": "shingle",
                                    "min_shingle_size": 5,
                                    "max_shingle_size": 5,
                                    "output_unigrams": False,
                                }
                            },
                            "tokenizer": {
                                "special_tokenizer": {
                                    "type": "simple_pattern_split",
                                    "pattern": self.special_connector,
                                }
                            },
                            "analyzer": {
                                "my_analyzer": {
                                    "filter": ["n_gram_filter"],
                                    "type": "custom",
                                    "tokenizer": "special_tokenizer",
                                }
                            },
                        }
                    },
                    "mappings": {
                        "properties": {
                            "repo_id": {
                                "index": True,
                                "type": "keyword",
                            },
                            "commit_sha": {"index": True, "type": "keyword"},
                            "filepath": {"index": True, "type": "keyword"},
                            "start_line": {"index": True, "type": "keyword"},
                            "end_line": {"index": True, "type": "keyword"},
                            "code": {
                                "type": "text",
                                "analyzer": "my_analyzer",
                                "search_analyzer": "my_analyzer",
                            },
                        }
                    },
                },
            )

    def create_handled_commit_index(self):
        if self.is_index_exists(
            index_name=self.config["elasticsearch"]["index_handled_commits"]
        ):
            return
        else:
            self.client.indices.create(
                index=self.config["elasticsearch"]["index_handled_commits"],
                body={
                    "mappings": {
                        "properties": {
                            "repo_id": {
                                "index": True,
                                "type": "keyword",
                            },
                            "commit_sha": {"index": True, "type": "keyword"},
                        }
                    }
                },
            )

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

    def concat_tokens(self, tokens: list, n=5):
        ngrams = []
        for i in range(0, len(tokens) - n + 1):
            ngram = (self.special_connector.join(tokens[i : i + n])).lower()
            ngrams.append(ngram)
        return ngrams

    def extract_es_infos(self, changed_methods: List[MethodInfo]):
        es_data_bulk = []  # used to store the extracted change
        # for changed methods, extract N-Gram list
        for changed_method in changed_methods:
            code = self.special_connector.join(changed_method.tokens).lower()
            # update the inverted index of elastic search
            es_data = {
                "_index": self.config["elasticsearch"]["index_ngram"],
                "doc": {
                    "repo_id": changed_method.repo_id,
                    "commit_sha": changed_method.commit_sha,
                    "filepath": changed_method.filepath.decode(),
                    "start_line": changed_method.start,
                    "end_line": changed_method.end,
                    "code": code,
                },
            }
            es_data_bulk.append(es_data)
        return es_data_bulk

    def location(self, n_grams: List[str]):
        pass

    def search_method(self, search_string: str):
        body = {"query": {"match": {"doc.code": {"query": search_string}}}}
        data = self.client.search(
            index=self.config["elasticsearch"]["index_ngram"], body=body
        )
        return data.body["hits"]["hits"]

    def search_method_filter(
        self, search_string: str, repo_id: int, filepath: str
    ):
        body = {
            "query": {
                "bool": {
                    "must": {"match": {"doc.code": {"query": search_string}}},
                    "must_not": [
                        {"match": {"doc.repo_id": repo_id}},
                        {"match": {"doc.filepath": filepath}},
                    ],
                }
            }
        }
        data = self.client.search(
            index=self.config["elasticsearch"]["index_ngram"], body=body
        )
        return data.body["hits"]["hits"]
