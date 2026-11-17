"""客服 Agent 主流程：模型选择工具 -> 执行 -> 工具结果回填模型 -> 生成回答。"""

import datetime

from model_client import ModelClient
from patient_store import find_by_identifier, login_patient_ref, resolve_authorized_patient
from privacy import find_identifiers, mask_identifier, mask_text
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

IDENTITY_PROMPT = "请先提供您本人或已授权家属的手机号或身份证号，以便确认身份。"
UNKNOWN_IDENTITY = "未查询到 {masked} 对应的患者，请确认手机号或身份证号。"
UNAUTHORIZED_REPLY = "该患者未获得当前登录身份的授权，无法查询。"
BAD_ARGUMENTS_REPLY = "查询条件不正确，请换一种说法。"


class CustomerServiceAgent:
    """一次会话一个实例：身份、上一轮结果与对话历史只在本会话内保留。"""

    def __init__(self, model_client=None):
        self.model = model_client or ModelClient()
        self.last_result = None
        self.patient_ref = None
        self.history = []

    def _system_message(self):
        return {
            "role": "system",
            "content": (
                f"你是医院客服助手，今天是 {datetime.date.today().isoformat()}。"
                "患者会用手机号或身份证号说明自己是谁，身份由系统确认；"
                "完整手机号、证件号不会提供给你，也不要向患者复述或猜测完整号码。"
                "根据患者问题选择合适的工具，参数为业务信息（如日期、科室）；"
                "patient_ref 由系统注入，无需提供。"
                "工具返回后用中文回答；多条结果按顺序编号，便于患者追问“第几条”。"
                "不要编造工具未返回的信息。"
            ),
            "tools": sorted(TOOLS),
        }

    def _confirm_identity(self, user_text):
        """在服务端解析手机号/身份证号（不发给模型），返回脱敏文本与错误回复。"""
        for raw in find_identifiers(user_text):
            patient_ref = find_by_identifier(raw)
            if patient_ref is None:
                return mask_text(user_text), UNKNOWN_IDENTITY.format(masked=mask_identifier(raw))
            try:
                resolve_authorized_patient(patient_ref)
            except PermissionError:
                return mask_text(user_text), UNAUTHORIZED_REPLY
            self.patient_ref = patient_ref
            break
        return mask_text(user_text), None

    def _remember(self, user_text, reply, tool_call=None, result=None):
        self.history.append({"role": "user", "content": user_text})
        if tool_call is not None:
            self.history.append({"role": "assistant", "tool_call": tool_call})
            self.history.append({"role": "tool", "name": tool_call["name"], "content": result})
        self.history.append({"role": "assistant", "content": reply})

    def answer(self, user_text):
        safe_text, error = self._confirm_identity(user_text)
        if error:
            self._remember(safe_text, error)
            return error

        messages = [self._system_message()] + self.history + [{"role": "user", "content": safe_text}]
        first = self.model.send(messages)
        if not isinstance(first, dict) or "tool" not in first:
            reply = first if isinstance(first, str) else "请说明您想查询的内容。"
            self._remember(safe_text, reply)
            return reply

        name = first["tool"]
        if name not in TOOLS:
            reply = "暂不支持该查询。"
            self._remember(safe_text, reply)
            return reply

        # 身份以服务端确认结果为准：本次解析 / 本会话此前解析 / 登录身份
        target_ref = self.patient_ref or login_patient_ref()
        if target_ref is None:
            self._remember(safe_text, IDENTITY_PROMPT)
            return IDENTITY_PROMPT

        arguments = dict(first.get("arguments") or {})
        arguments["patient_ref"] = target_ref
        try:
            result = TOOLS[name](**arguments)
        except PermissionError:
            self._remember(safe_text, UNAUTHORIZED_REPLY)
            return UNAUTHORIZED_REPLY
        except TypeError:
            self._remember(safe_text, BAD_ARGUMENTS_REPLY)
            return BAD_ARGUMENTS_REPLY
        self.last_result = result

        tool_call = {"name": name, "arguments": arguments}
        reply = self.model.send(messages + [
            {"role": "assistant", "tool_call": tool_call},
            {"role": "tool", "name": name, "content": result},
        ])
        self._remember(safe_text, reply, tool_call=tool_call, result=result)
        return reply
