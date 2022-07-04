# aim: the total number of java projects in GitHub community
# author: zhangxunhui
# date: 2022-06-22

import json
from datetime import datetime

import requests
import yaml

with open("test/config.yml", "r") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)


def query_projects():
    """
    url: https://api.github.com/search/repositories?q=language:java
    total_count: 10525321
    search time: 2022-06-22T12:16:25Z
    """
    url = "https://api.github.com/search/repositories?q=language:{language}".format(
        language="java"
    )
    print(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3941.4 Safari/537.36",
        "Authorization": "token " + config["token"],
        "Content-Type": "application/json",
        "method": "GET",
        "Accept": "application/vnd.github.squirrel-girl-preview+json",
    }

    response = requests.get(url=url, headers=headers)
    response.encoding = "utf-8"
    result = json.loads(response.text)
    print(result["total_count"])
    print(datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))


if __name__ == "__main__":
    query_projects()
    print("finish")
