"""患者身份：以手机号或身份证号作为唯一键；出境前脱敏。"""

import re

PATIENTS = {
    "P7": {"patient_id": 7001, "name": "张三丰(虚构)",
           "phone": "13900001234", "id_card": "110105199003074219"},
    "P8": {"patient_id": 7002, "name": "李四合(虚构)",
           "phone": "13800005678", "id_card": "310101198512061234"},
}

# 手机号 / 身份证号 -> patient_ref
_BY_PHONE = {p["phone"]: ref for ref, p in PATIENTS.items()}
_BY_ID_CARD = {p["id_card"]: ref for ref, p in PATIENTS.items()}

# 登录人（P7）与其已授权家属
SESSION = {"login_patient_ref": "P7", "authorized_refs": {"P7", "P8"}}

# 完整手机号 / 证件号：院内可以持有，但不允许发往外部模型（见 隐私与合规.md）
_PHONE_PATTERN = re.compile(r"(?<!\d)1\d{10}(?!\d)")
_ID_CARD_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")


def find_by_identifier(value):
    """用手机号或身份证号定位 patient_ref；找不到返回 None。"""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return _BY_PHONE.get(value) or _BY_ID_CARD.get(value)


def resolve_authorized_patient(patient_ref):
    if patient_ref not in SESSION["authorized_refs"]:
        raise PermissionError(f"当前登录身份无权访问 {patient_ref}")
    return PATIENTS[patient_ref]["patient_id"]


def mask_phone(phone):
    """手机号展示 / 出境格式：139****1234。"""
    return phone[:3] + "****" + phone[-4:]


def mask_id_card(id_card):
    """证件号展示 / 出境格式：110105********4219。"""
    return id_card[:6] + "********" + id_card[-4:]


def sanitize_text(text):
    """把文本中的完整手机号、证件号替换为掩码。"""
    text = _ID_CARD_PATTERN.sub(lambda match: mask_id_card(match.group()), text)
    return _PHONE_PATTERN.sub(lambda match: mask_phone(match.group()), text)


def sanitize_for_model(value):
    """递归脱敏 dict / list / 字符串，用于工具结果回填模型前。"""
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, dict):
        return {key: sanitize_for_model(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_for_model(item) for item in value]
    return value
