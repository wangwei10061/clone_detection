# aim: We randomly pick 100 projects and copy 361 times, we can get the fake projects.
# author: zhangxunhui
# date: 2022-06-22

import json
import random

import yaml

with open("test/config.yml", "r") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)


def random_projects():

    # 1. read all the projects
    with open("test/2_search_projects_in_the_day.json", "r") as f:
        projects = json.load(f)

    # 2. remove duplicates
    projects = list(set(projects))

    # 3. random pick 100 projects from the project set
    random_projects = random.sample(projects, 100)

    print(random_projects)


if __name__ == "__main__":
    random_projects()
    print("finish")
