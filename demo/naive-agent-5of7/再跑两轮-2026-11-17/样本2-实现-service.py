"""客服 Agent 主流程：模型选择工具 -> 执行 -> 工具结果回填模型 -> 生成回答。

患者身份在后端解析（patient_store.py）；发往外部模型的内容（用户原文、工具结果）
都先脱敏，完整手机号 / 证件号不出境（见 隐私与合规.md）。
追问依赖已脱敏的 self.history：每轮都连同之前的工具结果一起发给模型。
"""

from datetime import date

from model_client import ModelClient
from patient_store import (PATIENTS, SESSION, mask_id_card, mask_phone,
                           sanitize_for_model, sanitize_text)
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


class CustomerServiceAgent:
    def __init__(self, model_client=None, today=None):
        self.model = model_client or ModelClient()
        self.today = today or date.today()
        self.history = []  # 已脱敏的对话历史（含工具调用与结果），供连续追问
        self.last_result = None

    def _system_message(self):
        roster = "\n".join(
            f"- {ref}：手机号 {mask_phone(PATIENTS[ref]['phone'])}，"
            f"证件号 {mask_id_card(PATIENTS[ref]['id_card'])}"
            for ref in sorted(SESSION["authorized_refs"])
        )
        return {
            "role": "system",
            "content": (
                "你是医院客服助手。根据患者问题选择合适的工具，参数使用 patient_ref。"
                "工具返回后用中文回答。不要编造工具未返回的信息。\n"
                f"当前日期：{self.today}。\n"
                f"当前登录患者：{SESSION['login_patient_ref']}。"
                f"可访问患者（本人及已授权家属）：\n{roster}"
            ),
            "tools": sorted(TOOLS),
        }

    def answer(self, user_text):
        self.history.append({"role": "user", "content": sanitize_text(user_text)})
        first = self.model.send([self._system_message(), *self.history])
        if not isinstance(first, dict) or "tool" not in first:
            return self._reply(first if isinstance(first, str) else "请说明您想查询的内容。")

        name = first["tool"]
        if name not in TOOLS:
            return self._reply("暂不支持该查询。")
        arguments = first.get("arguments") or {}
        try:
            result = TOOLS[name](**arguments)
        except PermissionError:
            return self._reply("抱歉，当前登录身份无权查询该患者的信息。")
        self.last_result = result

        self.history.append({"role": "assistant",
                             "tool_call": {"name": name, "arguments": arguments}})
        self.history.append({"role": "tool", "name": name,
                             "content": sanitize_for_model(result)})
        return self._reply(self.model.send([self._system_message(), *self.history]))

    def _reply(self, text):
        text = sanitize_text(text)
        self.history.append({"role": "assistant", "content": text})
        return text
