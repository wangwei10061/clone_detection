# aim: invoke the search api to find test projects, here we consider java projects that have commits between 2022-05-21~2022-06-21. But only default branch is considered when searching for commit
# author: zhangxunhui
# date: 2022-06-21

import json
import operator
from datetime import datetime, timedelta, timezone

import requests
import yaml

with open("test/config.yml", "r") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)


def query_projects():
    """
    2022-5-20~2022-6-20有57437131个commit，数量太庞大了，只能缩小范围。
    2022-6-13~2022-6-20有11844199个commit，数量还减少了很多
    2022-6-13~2022-6-20有88092个java项目存在push操作
    To reduce the number of analyzed projects, we choose the day with the most number of push operations in the last year.
    """
    end_dt = datetime(
        year=2022,
        month=6,
        day=20,
        hour=0,
        minute=0,
        second=0,
        tzinfo=timezone.utc,
    )
    num_days = 365
    pushed_repo_count = {}  # key: pushed_gap, value: num
    for i in range(num_days):
        end_dt_i = end_dt - timedelta(days=i)
        start_dt_i = end_dt_i - timedelta(days=1)
        pushed = (
            start_dt_i.strftime("%Y-%m-%dT00:00:00Z")
            + ".."
            + end_dt_i.strftime("%Y-%m-%dT00:00:00Z")
        )
        url = "https://api.github.com/search/repositories?q=language:{language}+pushed:{pushed}&per_page=100&page={page}".format(
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
        total_count = result["total_count"]
        pushed_repo_count[pushed] = total_count

    sorted_pushed_repo_count = sorted(
        pushed_repo_count.items(), key=operator.itemgetter(1), reverse=True
    )  # sort by value
    print(sorted_pushed_repo_count)


if __name__ == "__main__":
    query_projects()
    print("finish")
