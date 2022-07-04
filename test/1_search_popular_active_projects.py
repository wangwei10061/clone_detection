# aim: to search java repositories that are popular and active in the last 24 hours; only select the top 100 projects as the simulator
# author: zhangxunhui
# date: 2022-06-22

import json
from datetime import datetime, timedelta

import requests
import yaml

with open("test/config.yml", "r") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

projects = []


def query_projects():
    """
    url: https://api.github.com/search/repositories?q=language:java+pushed:>=2022-06-21T12:19:49Z&sort=stars&order=desc&per_page=100&page=1
    total_count: 27406
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=1)
    pushed = ">=" + start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    url = "https://api.github.com/search/repositories?q=language:{language}+pushed:{pushed}&sort=stars&order=desc&per_page=100&page={page}".format(
        language="java", pushed=pushed, page=1
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
    projects.extend(result["items"])

    print(result["total_count"])

    with open("test/1_search_popular_active_projects.json", "w") as f:
        json.dump(projects, f)


if __name__ == "__main__":
    query_projects()
    print("finish")
