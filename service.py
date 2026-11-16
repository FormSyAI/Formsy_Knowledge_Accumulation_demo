"""客服 Agent 主流程：模型选择工具 -> 执行 -> 工具结果回填模型 -> 生成回答。"""

import re
from datetime import datetime, timedelta, timezone

from model_client import ModelClient
from patient_store import SESSION, find_by_identifier, resolve_authorized_patient
from tools.appointments import list_appointments
from tools.bills import list_bills
from tools.medications import list_medications
from tools.patient_profile import patient_profile

TOOLS = {
    "patient_profile": patient_profile,
    "list_medications": list_medications,
    "list_bills": list_bills,
    "list_appointments": list_appointments,
}

IDENTIFIER = re.compile(
    r"(?<![0-9０-９])"
    r"(?:(?:[0-9０-９][ 　－-]?){17}[0-9０-９XxＸｘ]|[1１](?:[ 　－-]?[0-9０-９]){10})"
    r"(?![0-9０-９])"
)
IDENTIFIER_WIDTH = str.maketrans("０１２３４５６７８９Ｘｘ　－", "0123456789Xx -")
HOSPITAL_TIMEZONE = timezone(timedelta(hours=8))


def _identifier_value(match):
    return match.group().translate(IDENTIFIER_WIDTH).replace(" ", "").replace("-", "").upper()


def _redact(value):
    if isinstance(value, str):
        def mask(match):
            identifier = _identifier_value(match)
            if len(identifier) == 11:
                return f"{identifier[:3]}****{identifier[-4:]}"
            return "[证件号已隐藏]"

        return IDENTIFIER.sub(mask, value)
    if isinstance(value, dict):
        return {_redact(key): _redact(item) for key, item in value.items()
                if key != "id_card"}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


class CustomerServiceAgent:
    def __init__(self, model_client=None):
        self.model = model_client or ModelClient()
        self.last_result = None
        self._login_ref = None
        self._patient_ref = None
        self._appointment_result = None

    def _system_message(self):
        today = datetime.now(HOSPITAL_TIMEZONE).date().isoformat()
        return {
            "role": "system",
            "content": (
                f"你是医院客服助手。今天是 {today}（北京时间）。根据患者问题选择工具。"
                "患者身份由服务端提供，无需传 patient_ref。"
                "查询预约使用 list_appointments，可传 date（YYYY-MM-DD）和 department（科室全称）。"
                "追问上一轮第几条预约时，只传从 1 开始的整数 index。"
                "预约列表按工具返回顺序编号。工具返回后用中文回答，不要编造信息。"
            ),
            "tools": sorted(TOOLS),
        }

    def answer(self, user_text):
        login_ref = SESSION["login_patient_ref"]
        if login_ref != self._login_ref:
            self._login_ref = login_ref
            self._patient_ref = None
            self._appointment_result = None
            self.last_result = None

        identifiers = {_identifier_value(match) for match in IDENTIFIER.finditer(user_text)}
        if identifiers:
            self._patient_ref = None
            self._appointment_result = None
            self.last_result = None
            refs = {find_by_identifier(identifier) for identifier in identifiers}
            if None in refs or len(refs) != 1:
                return "无法确定要查询的患者，请核对手机号或证件号。"
            self._patient_ref = refs.pop()

        patient_ref = self._patient_ref or login_ref
        try:
            resolve_authorized_patient(patient_ref)
        except (PermissionError, KeyError):
            self._appointment_result = None
            self.last_result = None
            return "当前登录身份无法查询该患者。"

        messages = [
            self._system_message(),
            {"role": "user", "content": _redact(user_text)},
        ]
        first = self.model.send(messages)
        if not isinstance(first, dict) or "tool" not in first:
            return _redact(first) if isinstance(first, str) else "请说明您想查询的内容。"

        name = first["tool"]
        if not isinstance(name, str) or name not in TOOLS:
            return "暂不支持该查询。"
        model_args = first.get("arguments") or {}
        if not isinstance(model_args, dict):
            return "请重新说明查询条件。"
        arguments = {"patient_ref": patient_ref}

        try:
            if name == "list_appointments" and "index" in model_args:
                index = model_args["index"]
                rows = (self._appointment_result or {}).get("appointments", [])
                if type(index) is not int or not 1 <= index <= len(rows):
                    return "上一轮预约结果中没有这条记录，请先查询预约列表。"
                arguments["index"] = index
                result = {"index": index, "appointment": rows[index - 1]}
            else:
                filters = {
                    "list_appointments": ("date", "department"),
                    "patient_profile": ("field",),
                }.get(name, ())
                for key in filters:
                    value = model_args.get(key)
                    if isinstance(value, str) and value.strip():
                        arguments[key] = value.strip()
                result = TOOLS[name](**arguments)
                if name == "list_appointments":
                    self._appointment_result = result
        except (PermissionError, KeyError):
            return "当前登录身份无法查询该患者。"

        self.last_result = _redact(result)
        response = self.model.send(messages + [
            {"role": "assistant", "tool_call": {"name": name, "arguments": _redact(arguments)}},
            {"role": "tool", "name": name, "content": self.last_result},
        ])
        return _redact(response) if isinstance(response, str) else "暂时无法生成查询结果。"
