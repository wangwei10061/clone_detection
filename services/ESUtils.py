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
        client = Elasticsearch(self.urls, request_timeout=3600)
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
                settings={
                    "similarity": {"default": {"type": "boolean"}},
                },
                mappings={
                    "properties": {
                        "repo_id": {"type": "integer"},
                        "commit_sha": {"type": "keyword"},
                        "filepath": {"type": "keyword"},
                        "start_line": {"type": "integer"},
                        "end_line": {"type": "integer"},
                        "created_at": {"type": "long"},
                        "code_ngrams": {"type": "keyword"},
                        "code": {"type": "text"},
                        "gram_num": {"type": "integer"},
                    }
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
                mappings={
                    "properties": {
                        "repo_id": {"type": "keyword"},
                        "commit_sha": {"type": "keyword"},
                    }
                },
            )

    def insert_es_bulk(self, bulk):
        helpers.bulk(self.client, bulk)

    def insert_es_item(self, item, index_name: str):
        self.client.index(index=index_name, body=item, refresh=True)

    def get_handled_commits(self, repo_id: int, index_name: str):
        handled_commits = set()
        body = {"query": {"term": {"repo_id": repo_id}}}
        scroll = "1m"
        size = 500
        if not self.client.indices.exists(index=index_name):
            return handled_commits  # index has not been created yet
        else:
            search_results = helpers.scan(
                client=self.client,
                index=index_name,
                body=body,
                scroll=scroll,
                size=size,
            )
            for hit in search_results:
                handled_commits.add(hit["_source"]["commit_sha"])
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
                "code_ngrams": changed_method.code_ngrams,
                "gram_num": changed_method.gram_num,
                "code": code,
            }
            actions.append(action)
        return actions

    def search_method_filter(self, method: MethodInfo):
        query = {
            "query": {
                "bool": {
                    "must": {
                        "terms_set": {
                            "code_ngrams": {
                                "terms": method.code_ngrams,
                                "minimum_should_match_script": {
                                    "source": "Math.ceil(Math.min(params.num_terms, doc['gram_num'].value) * 0.1)"
                                },
                            }
                        }
                    },
                    "must_not": [
                        {"match": {"repo_id": method.repo_id}},
                        {"match": {"filepath": method.filepath.decode()}},
                    ],
                }
            }
        }
        search_results = helpers.scan(
            client=self.client,
            query=query,
            scroll="1m",
            index=self.config["elasticsearch"]["index_ngram"],
        )
        return search_results

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
