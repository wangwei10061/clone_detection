# aim: The utilities of services
# author: zhangxunhui
# date: 2022-04-23

import yaml
from elasticsearch import Elasticsearch, helpers


def read_config(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
            return config
    except Exception:
        return None


def read_variable_length_bytes(readF):
    """This function is used to read all the bytes that related to variable length integers."""
    result = []
    while len(result) == 0 or result[-1] & 0x80:
        result.append(readF(1)[0])
    return result


def connect_es(config):
    urls = config["elasticsearch"]["url"]
    client = Elasticsearch(urls)
    return client


def insert_es_bulk(client, bulk):
    helpers.bulk(client, bulk)
