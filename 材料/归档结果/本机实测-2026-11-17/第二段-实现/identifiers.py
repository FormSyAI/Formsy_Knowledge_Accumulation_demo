"""手机号/证件号识别、宽度归一化与脱敏：查找患者与模型边界共用同一套规则。"""

import re

IDENTIFIER = re.compile(
    r"(?<![0-9０-９])"
    r"(?:(?:[0-9０-９][ 　－-]?){17}[0-9０-９XxＸｘ]|[1１](?:[ 　－-]?[0-9０-９]){10})"
    r"(?![0-9０-９])"
)
IDENTIFIER_WIDTH = str.maketrans("０１２３４５６７８９Ｘｘ　－", "0123456789Xx -")


def identifier_value(match):
    return match.group().translate(IDENTIFIER_WIDTH).replace(" ", "").replace("-", "").upper()


def redact(value):
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
