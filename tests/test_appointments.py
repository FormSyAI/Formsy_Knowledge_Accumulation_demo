import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from model_client import ModelClient
from patient_store import PATIENTS, SESSION
from service import HOSPITAL_TIMEZONE, CustomerServiceAgent
from tools.appointments import list_appointments


class AppointmentTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(dir=".")
        self.addCleanup(directory.cleanup)
        self.log = Path(directory.name) / "requests.jsonl"
        self.agent = CustomerServiceAgent(ModelClient(str(self.log)))
        clock = patch("service.datetime")
        clock.start().now.return_value = datetime(2026, 11, 16, tzinfo=HOSPITAL_TIMEZONE)
        self.addCleanup(clock.stop)

    def test_phone_and_tomorrow_filter(self):
        answer = self.agent.answer(f"{PATIENTS['P7']['phone']}，明天有什么预约？")
        self.assertIn("09:30", answer)
        self.assertNotIn("14:00", answer)
        self.assertIn("139****1234", self.log.read_text())

    def test_family_id_card_and_department_filter(self):
        answer = self.agent.answer(f"帮我查 {PATIENTS['P8']['id_card']} 的内科预约")
        self.assertIn("10:15", answer)
        self.assertNotIn("09:30", answer)
        self.assertEqual(self.agent.answer("明天有口腔科预约吗？"), "未查到符合条件的预约。")

    def test_followup_uses_order_of_filtered_results(self):
        first = self.agent.answer("有什么预约？")
        self.assertLess(first.index("内科"), first.index("口腔科"))
        self.assertIn("口腔科", self.agent.answer("刚才那个人第二条是哪个科室？"))
        self.agent.answer("明天有什么预约？")
        self.assertIn("没有这条记录", self.agent.answer("第二条是哪个科室？"))

    def test_tomorrow_with_two_rows(self):
        extra = {"patient_ref": "P7", "date": "2026-11-17", "time": "15:00",
                 "department": "口腔科", "status": "已预约"}
        with patch.dict("hospital_api.APPOINTMENTS", {"extra": extra}):
            self.agent.answer("明天有什么预约？")
        self.assertIn("口腔科", self.agent.answer("第二条是哪个科室？"))

    def test_revoked_family_access_and_login_switch(self):
        self.agent.answer(f"{PATIENTS['P8']['phone']}，明天有什么预约？")
        with patch.dict(SESSION, {"authorized_refs": {"P7"}}):
            self.assertIn("无法查询", self.agent.answer("第一条是哪个科室？"))
            self.assertIn("无法查询", self.agent.answer(f"{PATIENTS['P8']['phone']}的预约"))
        with patch.dict(SESSION, {"login_patient_ref": "P8", "authorized_refs": {"P8"}}):
            self.assertIn("没有这条记录", self.agent.answer("第一条是哪个科室？"))

    def test_unknown_identifier_does_not_fall_back_to_logged_in_patient(self):
        self.assertIn("无法确定", self.agent.answer("13700000000，明天有什么预约？"))
        self.assertFalse(self.log.exists())

    def test_identifier_variants_are_redacted_in_both_model_requests(self):
        cases = (
            ("139 0000 1234", "139****1234", "09:30"),
            ("139-0000-1234", "139****1234", "09:30"),
            ("１３９００００１２３４", "139****1234", "09:30"),
            ("１３9－0000　１２３４", "139****1234", "09:30"),
            ("３１０１０１１９８５１２０６１２３４", "[证件号已隐藏]", "10:15"),
            ("３１０１０１－19851206　１２３４", "[证件号已隐藏]", "10:15"),
        )
        for identifier, masked, appointment_time in cases:
            with self.subTest(identifier=identifier):
                self.log.write_text("", encoding="utf-8")
                answer = self.agent.answer(f"{identifier}，查询明天的预约")
                requests = self.log.read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(requests), 2)
                for request in requests:
                    self.assertNotIn(identifier, request)
                    messages = json.loads(request)["messages"]
                    self.assertEqual(messages[1]["content"], f"{masked}，查询明天的预约")
                self.assertIn(appointment_time, answer)

    def test_model_cannot_override_patient_and_payloads_are_redacted(self):
        patient = PATIENTS["P7"]
        for tool in ("patient_profile", "list_medications", "list_bills", "list_appointments"):
            with self.subTest(tool=tool):
                original_send = self.agent.model.send
                first = {"tool": tool, "arguments": {"patient_ref": "P8"}}

                def send(messages):
                    response = original_send(messages)
                    return first if messages[-1]["role"] == "user" else response

                with patch.object(self.agent.model, "send", side_effect=send):
                    self.agent.answer(f"{patient['phone']} {patient['id_card']} 查询")
                requests = [json.loads(line)["messages"] for line in self.log.read_text().splitlines()]
                self.assertEqual(requests[-1][-2]["tool_call"]["arguments"]["patient_ref"], "P7")
                for messages in requests:
                    payload = json.dumps(messages, ensure_ascii=False)
                    self.assertNotIn(patient["phone"], payload)
                    self.assertNotIn(patient["id_card"], payload)

    def test_appointment_tool_returns_only_business_fields(self):
        result = list_appointments("P7", date="2026-11-17", department="内科")
        self.assertEqual(result, {"appointments": [{
            "date": "2026-11-17", "time": "09:30", "department": "内科", "status": "已预约",
        }]})
        with self.assertRaises(PermissionError):
            list_appointments("P9")
