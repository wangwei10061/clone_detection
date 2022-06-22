# aim: 2022-02-10T00:00:00Z..2022-02-11T00:00:00Z. There are 36,098 projects changed.
# author: zhangxunhui
# date: 2022-06-22

import json
import time
from datetime import datetime, timedelta, timezone

import requests
import yaml

with open("test/config.yml", "r") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)


def query_projects():
    projects = []
    end_dt = datetime(
        year=2022,
        month=2,
        day=11,
        hour=0,
        minute=0,
        second=0,
        tzinfo=timezone.utc,
    )
    num_minutes = 60 * 24
    for i in range(num_minutes):
        end_dt_i = end_dt - timedelta(minutes=i)
        start_dt_i = end_dt_i - timedelta(minutes=1)
        pushed = (
            start_dt_i.strftime("%Y-%m-%dT%H:%M:%SZ")
            + ".."
            + end_dt_i.strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        which_page = 1
        count = 100
        while count >= 100:
            url = "https://api.github.com/search/repositories?q=language:{language}+pushed:{pushed}&per_page=100&page={page}".format(
                language="java", pushed=pushed, page=which_page
            )
            if which_page > 10:
                print("Error with this url: {url}".format(url=url))
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
            if "total_count" in result:
                count = result["total_count"]
            else:
                count = 0
            if count > 0:
                projects.extend(result["items"])
            which_page += 1
            time.sleep(0.1)

    with open("test/2_search_projects_in_the_day.json", "w") as f:
        json.dump(projects, f)


if __name__ == "__main__":
    query_projects()
    print("finish")
