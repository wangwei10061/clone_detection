# 判断NIL与LSICCDS的结果是否是一致的

import os

import pandas as pd

NIL_result = pd.read_csv("result_5_10_70.csv", header=None, index_col=None)
NIL_result.columns = [
    "filepath1",
    "start1",
    "end1",
    "filepath2",
    "start2",
    "end2",
]

LSICCDS_result = {
    "filepath1": [],
    "start1": [],
    "end1": [],
    "filepath2": [],
    "start2": [],
    "end2": [],
}
with open("test/test_speed_middle_results/LSICCDS_clone_pairs", "r") as f:
    content = f.read()
    content = content.strip().split("\n")
    for line in content:
        first, second = line.split(";")
        filepath1, start1, end1 = first.split(",")
        filepath2, start2, end2 = second.split(",")
        LSICCDS_result["filepath1"].append(
            os.path.join(
                "/home/zxh/programs/LSICCDS/LSICCDS_server", filepath1
            )
        )
        LSICCDS_result["start1"].append(int(start1))
        LSICCDS_result["end1"].append(int(end1))
        LSICCDS_result["filepath2"].append(
            os.path.join(
                "/home/zxh/programs/LSICCDS/LSICCDS_server", filepath2
            )
        )
        LSICCDS_result["start2"].append(int(start2))
        LSICCDS_result["end2"].append(int(end2))
LSICCDS_result = pd.DataFrame.from_dict(LSICCDS_result)


def find_unique_results(df1: pd.DataFrame, df2: pd.DataFrame):
    """Unique in df1."""
    diffs = []
    for row in df1.itertuples():
        filepath1 = row.filepath1
        start1 = row.start1
        end1 = row.end1
        filepath2 = row.filepath2
        start2 = row.start2
        end2 = row.end2
        rows = df2[
            (
                (df2["filepath1"] == filepath1)
                & (df2["start1"] == start1)
                & (df2["end1"] == end1)
                & (df2["filepath2"] == filepath2)
                & (df2["start2"] == start2)
                & (df2["end2"] == end2)
            )
            | (
                (df2["filepath1"] == filepath2)
                & (df2["start1"] == start2)
                & (df2["end1"] == end2)
                & (df2["filepath2"] == filepath1)
                & (df2["start2"] == start1)
                & (df2["end2"] == end1)
            )
        ]
        if len(rows) == 0:
            diffs.append(row)
    return diffs


print("找到LSICCDS中有的而NIL中没有的结果")
diffs = find_unique_results(LSICCDS_result, NIL_result)

print("找到NIL中有而LSICCDS中没有的结果")
diffs = find_unique_results(NIL_result, LSICCDS_result)
print("finish")
