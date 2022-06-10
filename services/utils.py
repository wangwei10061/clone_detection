# aim: The utilities of services
# author: zhangxunhui
# date: 2022-04-23

from datetime import datetime, timezone

import yaml


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


def is_file_supported(filepath: str, lang_suffix: list):
    for suffix in lang_suffix:
        if filepath.endswith(suffix):
            return True
    return False


def extract_n_grams(tokens: str, ngramSize: int):
    ngrams = []
    for i in range(len(tokens) - ngramSize + 1):
        ngrams.append(" ".join(tokens[i : i + ngramSize]))
    return ngrams


def convert_time2utc(t, tz):
    return (
        t - tz
    )  # because the timezone in dulwich.objects.Commit is already in second scale


if __name__ == "__main__":
    print(convert_time2utc(1319140312, 0))
