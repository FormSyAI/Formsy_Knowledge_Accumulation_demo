"""预约查询工具与客服 Agent 预约流程的测试。"""

import json
import unittest

from patient_store import SESSION
from service import IDENTITY_PROMPT, CustomerServiceAgent
from tests.helpers import RecordingModel
from tools.appointments import list_appointments

PHONE_P7 = "13900001234"
ID_CARD_P7 = "110105199003074219"
PHONE_P8 = "13800005678"


def requests_text(model):
    return json.dumps(model.requests, ensure_ascii=False)


class AppointmentToolTests(unittest.TestCase):
    def test_filter_by_date_and_department(self):
        by_date = list_appointments("P7", date="2026-11-18")
        self.assertEqual(["内科", "口腔科"], [row["department"] for row in by_date["appointments"]])

        by_department = list_appointments("P7", department="口腔")
        self.assertEqual(["A13"], [row["appointment_id"] for row in by_department["appointments"]])

        combined = list_appointments("P7", date="2026-11-18", department="内科")
        self.assertEqual(["A14"], [row["appointment_id"] for row in combined["appointments"]])

    def test_appointments_sorted_and_patient_masked(self):
        result = list_appointments("P7")
        times = [(row["date"], row["time"]) for row in result["appointments"]]
        self.assertEqual(sorted(times), times)
        self.assertEqual("张三丰(虚构)", result["patient"]["name"])
        self.assertEqual("139****1234", result["patient"]["phone"])
        self.assertEqual("110105********4219", result["patient"]["id_card"])
        self.assertNotIn("patient_ref", result["appointments"][0])

    def test_unauthorized_ref_rejected(self):
        with self.assertRaises(PermissionError):
            list_appointments("P9")


class AppointmentFlowTests(unittest.TestCase):
    def test_phone_query_and_follow_up(self):
        model = RecordingModel([
            {"tool": "list_appointments", "arguments": {"date": "2026-11-18"}},
            "明天有 2 条预约：1. 10:30 内科；2. 14:00 口腔科。",
            "第二条是口腔科。",
        ])
        agent = CustomerServiceAgent(model_client=model)

        answer = agent.answer(f"{PHONE_P7}，明天有什么预约？")
        self.assertIn("2 条预约", answer)
        self.assertEqual(["A14", "A13"],
                         [row["appointment_id"] for row in agent.last_result["appointments"]])

        # 身份由服务端解析：模型只看到脱敏手机号，工具参数用服务端确认的 patient_ref
        first_request = json.dumps(model.requests[0], ensure_ascii=False)
        self.assertIn("139****1234", first_request)
        self.assertNotIn(PHONE_P7, first_request)
        self.assertEqual("P7", model.requests[1][-2]["tool_call"]["arguments"]["patient_ref"])

        # 连续追问：不用重复身份，模型可从上一轮工具结果中定位“第二条”
        follow_up = agent.answer("刚才那个人第二条是哪个科室？")
        self.assertEqual("第二条是口腔科。", follow_up)
        context = json.dumps(model.requests[2], ensure_ascii=False)
        self.assertIn("明天有 2 条预约", context)
        self.assertIn('"A13"', context)

    def test_id_card_query(self):
        model = RecordingModel([
            {"tool": "list_appointments", "arguments": {}},
            "您共有 3 条预约。",
        ])
        agent = CustomerServiceAgent(model_client=model)
        agent.answer(f"帮我查 {ID_CARD_P7} 的预约")

        self.assertEqual(3, len(agent.last_result["appointments"]))
        self.assertEqual(7001, agent.last_result["patient"]["patient_id"])
        self.assertNotIn(ID_CARD_P7, requests_text(model))
        self.assertIn("110105********4219", requests_text(model))

    def test_authorized_family_member_and_session_sticks(self):
        model = RecordingModel([
            {"tool": "list_appointments", "arguments": {"patient_ref": "P7"}},
            "李四合有 1 条预约。",
            {"tool": "list_appointments", "arguments": {}},
            "还是这 1 条。",
        ])
        agent = CustomerServiceAgent(model_client=model)

        agent.answer(f"帮我查 {PHONE_P8} 的预约")
        # 即使模型给错 patient_ref，也以服务端解析结果（已授权家属 P8）为准
        self.assertEqual("李四合(虚构)", agent.last_result["patient"]["name"])
        self.assertEqual("P8", model.requests[1][-2]["tool_call"]["arguments"]["patient_ref"])
        self.assertNotIn(PHONE_P8, requests_text(model))

        # 同一会话的后续追问继续落在该家属身上
        agent.answer("还有别的预约吗？")
        self.assertEqual("P8", model.requests[3][-2]["tool_call"]["arguments"]["patient_ref"])
        self.assertEqual("李四合(虚构)", agent.last_result["patient"]["name"])

    def test_query_without_identifier_uses_login_identity(self):
        model = RecordingModel([
            {"tool": "list_appointments", "arguments": {"date": "2026-11-18"}},
            "明天有 2 条预约。",
        ])
        agent = CustomerServiceAgent(model_client=model)
        agent.answer("明天有什么预约？")
        self.assertEqual("P7", model.requests[1][-2]["tool_call"]["arguments"]["patient_ref"])

    def test_rejects_unknown_identifier_without_calling_model(self):
        model = RecordingModel(["不应被调用"])
        agent = CustomerServiceAgent(model_client=model)
        answer = agent.answer("帮我查 13900009999 的预约")
        self.assertIn("未查询到", answer)
        self.assertIn("139****9999", answer)
        self.assertEqual([], model.requests)
        self.assertIsNone(agent.last_result)

    def test_unauthorized_identifier_rejected(self):
        model = RecordingModel(["不应被调用"])
        agent = CustomerServiceAgent(model_client=model)
        original_refs = SESSION["authorized_refs"]
        SESSION["authorized_refs"] = {"P7"}
        try:
            answer = agent.answer(f"帮我查 {PHONE_P8} 的预约")
        finally:
            SESSION["authorized_refs"] = original_refs
        self.assertIn("授权", answer)
        self.assertEqual([], model.requests)

    def test_without_any_available_identity_asks_first(self):
        model = RecordingModel([
            {"tool": "list_appointments", "arguments": {"date": "2026-11-18"}},
            {"tool": "list_appointments", "arguments": {"date": "2026-11-18"}},
            "明天有 2 条预约。",
        ])
        agent = CustomerServiceAgent(model_client=model)
        original_login = SESSION["login_patient_ref"]
        SESSION["login_patient_ref"] = "P9"
        try:
            answer = agent.answer("明天有什么预约？")
        finally:
            SESSION["login_patient_ref"] = original_login
        self.assertEqual(IDENTITY_PROMPT, answer)
        self.assertIsNone(agent.last_result)

        # 补上身份后可以继续查询
        answer = agent.answer(f"{PHONE_P7}，明天有什么预约？")
        self.assertEqual("明天有 2 条预约。", answer)
        self.assertEqual(2, len(agent.last_result["appointments"]))


if __name__ == "__main__":
    unittest.main()
