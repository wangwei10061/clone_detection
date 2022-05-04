# aim: The utilities of services
# author: zhangxunhui
# date: 2022-04-23

import yaml

def read_config(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
            return config
    except Exception:
        return None


def read_variable_length_bytes(readF):
    """This function is used to read all the bytes that related to variable length integers.
    """
    result = []
    while len(result) == 0 or result[-1] & 0x80:
        result.append(readF(1)[0])
    return result