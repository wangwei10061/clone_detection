# aim: The utilities of elastic search operations
# author: zhangxunhui
# date: 2022-05-27

import os
from typing import List

import yaml
from elasticsearch import Elasticsearch, helpers
from models.MethodInfo import MethodInfo


class ESUtils(object):
    def __init__(self, config: dict):
        self.config = config
        self.urls = self.config["elasticsearch"]["urls"]
        self.client = self.connect()

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
                                "my_shingle_filter": {
                                    "type": "shingle",
                                    "min_shingle_size": self.config["service"][
                                        "ngram"
                                    ],
                                    "max_shingle_size": self.config["service"][
                                        "ngram"
                                    ],
                                    "output_unigrams": "false",
                                }
                            },
                            "analyzer": {
                                "shingle_analyzer": {
                                    "filter": [
                                        "lowercase",
                                        "my_shingle_filter",
                                    ],
                                    "type": "custom",
                                    "tokenizer": "whitespace",
                                }
                            },
                        }
                    },
                    "mappings": {
                        "properties": {
                            "repo_id": {"type": "integer"},
                            "commit_sha": {"type": "keyword"},
                            "filepath": {"type": "keyword"},
                            "start_line": {"type": "integer"},
                            "end_line": {"type": "integer"},
                            "created_at": {"type": "long"},
                            "code_ngrams": {
                                "type": "text",
                                "analyzer": "shingle_analyzer",
                                "search_analyzer": "shingle_analyzer",
                            },
                            "code": {"index": False, "type": "text"},
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
                            "repo_id": {"type": "keyword"},
                            "commit_sha": {"type": "keyword"},
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
            self.client.clear_scroll(scroll_id=scroll_id)
            return list(handled_commits)

    def extract_es_infos(self, changed_methods: List[MethodInfo]):
        actions = []  # used to store the extracted change
        # for changed methods, extract N-Gram list
        for changed_method in changed_methods:
            code = " ".join(changed_method.tokens)
            # update the inverted index of elastic search
            action = {
                "_op_type": "create",
                "_index": self.config["elasticsearch"]["index_ngram"],
                "repo_id": changed_method.repo_id,
                "commit_sha": changed_method.commit_sha,
                "created_at": changed_method.created_at,
                "filepath": changed_method.filepath.decode(),
                "start_line": changed_method.start,
                "end_line": changed_method.end,
                "code_ngrams": code,
                "code": code,
            }
            actions.append(action)
        return actions

    def search_method(self, search_string: str):
        body = {"query": {"match": {"code_ngrams": {"query": search_string}}}}
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
                    "must": {
                        "match": {"code_ngrams": {"query": search_string}}
                    },
                    "must_not": [
                        {"match": {"repo_id": repo_id}},
                        {"match": {"filepath": filepath}},
                    ],
                }
            }
        }
        data = self.client.search(
            index=self.config["elasticsearch"]["index_ngram"], body=body
        )
        return data.body["hits"]["hits"]

    def delete_index(self, index_name):
        if self.is_index_exists(index_name=index_name):
            self.client.indices.delete(index=index_name)


if __name__ == "__main__":
    config_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "config.yml"
    )
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    es = ESUtils(config=config)
    es.delete_index("n_grams_test4")
    print("finish")
