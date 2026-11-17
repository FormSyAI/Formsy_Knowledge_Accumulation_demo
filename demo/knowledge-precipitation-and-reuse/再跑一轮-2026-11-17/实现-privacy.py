"""患者身份号码的识别与脱敏。

定位患者与发往模型前的脱敏共用同一套规则，避免"一处改了、另一处还漏"。
规则覆盖全角数字与全角分隔符（全角写法表达的是同一个号码）。
"""

import re

IDENTIFIER = re.compile(
    r"(?<![0-9０-９])"
    r"(?:(?:[0-9０-９][ 　－-]?){17}[0-9０-９XxＸｘ]|[1１](?:[ 　－-]?[0-9０-９]){10})"
    r"(?![0-9０-９])"
)
IDENTIFIER_WIDTH = str.maketrans("０１２３４５６７８９Ｘｘ　－", "0123456789Xx -")


def identifier_value(match):
    """号码的可比较形式：全角转半角、去掉分隔符、大写。"""
    return match.group().translate(IDENTIFIER_WIDTH).replace(" ", "").replace("-", "").upper()


def redact(value):
    """手机号替换为 139****1234、证件号替换为 [证件号已隐藏]。

    字典丢弃 id_card 键，列表逐项处理，其余原样返回。
    """
    if isinstance(value, str):
        def mask(match):
            identifier = identifier_value(match)
            if len(identifier) == 11:
                return f"{identifier[:3]}****{identifier[-4:]}"
            return "[证件号已隐藏]"

        return IDENTIFIER.sub(mask, value)
    if isinstance(value, dict):
        return {redact(key): redact(item) for key, item in value.items()
                if key != "id_card"}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value
