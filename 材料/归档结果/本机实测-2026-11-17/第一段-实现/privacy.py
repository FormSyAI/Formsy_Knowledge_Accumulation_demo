"""隐私与合规：完整手机号、证件号不得发往外部模型，页面只展示脱敏形式。"""

import re

_PHONE_PATTERN = r"1[3-9]\d{9}"
_ID_CARD_PATTERN = r"\d{17}[\dXx]"

# 身份证号可能包含与手机号形似的子串，识别时证件号优先，且不做重叠匹配。
IDENTIFIER_RE = re.compile(rf"(?P<id_card>{_ID_CARD_PATTERN})|(?P<phone>{_PHONE_PATTERN})")


def mask_phone(phone):
    """13900001234 -> 139****1234"""
    if not isinstance(phone, str) or len(phone) < 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"


def mask_id_card(id_card):
    """110105199003074219 -> 110105********4219"""
    if not isinstance(id_card, str) or len(id_card) < 11:
        return id_card
    return f"{id_card[:6]}{'*' * (len(id_card) - 10)}{id_card[-4:]}"


def mask_identifier(value):
    """脱敏单个手机号或证件号；未知格式原样返回。"""
    if not isinstance(value, str):
        return value
    value = value.strip()
    if re.fullmatch(_ID_CARD_PATTERN, value):
        return mask_id_card(value)
    if re.fullmatch(_PHONE_PATTERN, value):
        return mask_phone(value)
    return value


def find_identifiers(text):
    """按出现顺序返回文本中的完整手机号/证件号。"""
    if not isinstance(text, str):
        return []
    return [match.group() for match in IDENTIFIER_RE.finditer(text)]


def mask_text(text):
    """把文本中的完整手机号/证件号替换为脱敏形式。"""
    if not isinstance(text, str):
        return text
    return IDENTIFIER_RE.sub(
        lambda match: mask_phone(match.group()) if match.group("phone")
        else mask_id_card(match.group()),
        text,
    )


def mask_patient(patient):
    """复制患者记录并脱敏手机号、证件号（发给模型前使用）。"""
    masked = dict(patient)
    if "phone" in masked:
        masked["phone"] = mask_phone(masked["phone"])
    if "id_card" in masked:
        masked["id_card"] = mask_id_card(masked["id_card"])
    return masked
