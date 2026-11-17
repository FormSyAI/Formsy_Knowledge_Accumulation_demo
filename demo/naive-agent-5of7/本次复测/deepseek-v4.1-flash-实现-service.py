"""客服 Agent 主流程：模型选择工具 -> 执行 -> 工具结果回填模型 -> 生成回答。

患者身份在本地解析：消息里的完整手机号 / 证件号不发送给模型，
模型只看到 patient_ref 与打码后的联系方式（见 隐私与合规.md）。
"""

import re
from datetime import date

from model_client import ModelClient
from patient_store import SESSION, find_by_identifier, public_patient
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

# 二代身份证号与手机号；取消息里最先出现的那个作为说话人身份
_ID_CARD_RE = re.compile(r"[1-9]\d{16}[\dXx]")
_PHONE_RE = re.compile(r"1[3-9]\d{9}")

_IDENTITY_PLACEHOLDER = "[身份已识别]"
_NOT_FOUND = "没有找到您可查看的就诊人，请确认手机号或证件号，或先为家属完成授权。"
_BAD_ARGUMENTS = "抱歉，我没能理解这条查询条件，请换一种说法。"
_NOT_SUPPORTED = "暂不支持该查询。"


class CustomerServiceAgent:
    def __init__(self, model_client=None, today=None):
        self.model = model_client or ModelClient()
        self.login_ref = SESSION["login_patient_ref"]
        self.today = today or date.today()
        self.current_ref = None  # 上一轮查询的就诊人，用于"刚才那个人"
        self.last_tool = None
        self.last_result = None

    def answer(self, user_text):
        text, mentioned_ref, error = self._resolve_identity(user_text)
        if error:
            return error
        default_ref = mentioned_ref or self.current_ref or self.login_ref
        messages = [
            self._system_message(default_ref, mentioned_ref),
            {"role": "user", "content": text},
        ]

        first = self.model.send(messages)
        if not isinstance(first, dict) or "tool" not in first:
            return first if isinstance(first, str) else "请说明您想查询的内容。"

        name = first["tool"]
        if name not in TOOLS:
            return _NOT_SUPPORTED
        arguments = dict(first.get("arguments") or {})
        if not arguments.get("patient_ref"):
            arguments["patient_ref"] = default_ref
        try:
            result = TOOLS[name](**arguments)
        except PermissionError:
            return _NOT_FOUND
        except (TypeError, ValueError):
            return _BAD_ARGUMENTS
        self.last_tool = name
        self.last_result = result
        self.current_ref = arguments["patient_ref"]

        return self.model.send(messages + [
            {"role": "assistant", "tool_call": {"name": name, "arguments": arguments}},
            {"role": "tool", "name": name, "content": result},
        ])

    def _resolve_identity(self, user_text):
        """把消息里的手机号 / 证件号在本地换成 patient_ref，并对模型隐藏原文。"""
        match = self._find_identifier(user_text)
        if match is None:
            return user_text, None, None
        ref = find_by_identifier(match.group())
        if ref is None or ref not in SESSION["authorized_refs"]:
            return None, None, _NOT_FOUND
        redacted = f"{user_text[:match.start()]}{_IDENTITY_PLACEHOLDER}{user_text[match.end():]}"
        return redacted, ref, None

    @staticmethod
    def _find_identifier(text):
        matches = [m for m in (_ID_CARD_RE.search(text), _PHONE_RE.search(text)) if m]
        return min(matches, key=lambda m: m.start()) if matches else None

    def _system_message(self, default_ref, mentioned_ref):
        lines = [
            "你是医院客服助手。根据患者问题选择合适的工具，参数使用 patient_ref。",
            "工具返回后用中文回答。不要编造工具未返回的信息。",
            "不要输出完整手机号或证件号，手机号写成 139****1234 这种形式。",
            "患者消息里的手机号 / 证件号已由系统识别为下方就诊人，不发送原文给你。",
            f"今天日期：{self.today.isoformat()}。",
            "可访问就诊人：" + "；".join(f"{ref}（{self._describe(ref)}）"
                                        for ref in sorted(SESSION["authorized_refs"])),
            f"本轮默认就诊人：{default_ref}（{self._describe(default_ref)}，"
            f"{self._default_reason(mentioned_ref)}）。",
        ]
        if self.current_ref:
            lines.append(f"上一轮查询就诊人：{self.current_ref}（{self._describe(self.current_ref)}）。")
        previous = self._previous_appointments_line()
        if previous:
            lines.append(previous)
        return {"role": "system", "content": "\n".join(lines), "tools": sorted(TOOLS)}

    def _describe(self, ref):
        patient = public_patient(ref)
        return f"{patient['name']}，{patient['phone']}，{'本人' if ref == self.login_ref else '家属'}"

    def _default_reason(self, mentioned_ref):
        if mentioned_ref:
            return "用户本轮提到的身份"
        if self.current_ref:
            return "延续上一轮查询"
        return "登录患者"

    def _previous_appointments_line(self):
        if self.last_tool != "list_appointments" or not self.last_result:
            return None
        rows = self.last_result.get("appointments") or []
        if not rows:
            return "上一轮预约查询结果：没有符合条件的预约。"
        items = "；".join(f"{index}. {row['date']} {row['time']} {row['department']} {row['status']}"
                          for index, row in enumerate(rows, 1))
        return f"上一轮预约查询结果（按时间顺序，与患者看到的编号一致）：{items}。"
