"""检查报告解读：本机留存、归属校验、脱敏与权限的测试。"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import report_store
from model_client import ModelClient
from patient_store import PATIENTS, SESSION
from report_ocr import REPORTS
from report_store import (
    ReportOwnershipError,
    UnknownReportError,
    ingest_report,
    load_raw_report,
)
from service import CustomerServiceAgent
from tools.reports import read_report

FULL_ID = "３１０１０１－19851206　１２３４"
UPLOAD = {
    "patient_header": f"姓名：李四合(虚构)　证件号：{FULL_ID}　手机：13800005678",
    "items": [
        {"name": "空腹血糖", "value": "6.8", "unit": "mmol/L", "ref": "3.9-6.1"},
        {"name": "总胆固醇", "value": "5.2", "unit": "mmol/L", "ref": "<5.2"},
    ],
}


class ReportTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(dir=".")
        self.addCleanup(directory.cleanup)
        self.dir = Path(directory.name)
        patch.object(report_store, "REPORT_DIR", str(self.dir / "reports")).start()
        patch.dict(REPORTS, {"UP1": UPLOAD}).start()
        patch.dict(SESSION, {"login_patient_ref": "P7", "authorized_refs": {"P7", "P8"}},
                   clear=True).start()
        self.addCleanup(patch.stopall)
        self.log = self.dir / "requests.jsonl"
        self.agent = CustomerServiceAgent(ModelClient(str(self.log)))

    def test_upload_keeps_raw_report_locally_and_returns_ref(self):
        report_ref = ingest_report("P8", "UP1", image_path=str(self.dir / "upload.jpg"))
        self.assertRegex(report_ref, r"RPT-[0-9]{4,}")
        stored = json.loads((self.dir / "reports" / f"{report_ref}.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["patient_ref"], "P8")
        self.assertEqual(stored["source_ref"], "UP1")
        self.assertTrue(stored["verified"])
        self.assertIn("upload.jpg", stored["image_path"])
        self.assertIn(FULL_ID, stored["ocr"]["patient_header"])
        self.assertEqual(load_raw_report(report_ref)["ocr"]["items"], UPLOAD["items"])

    def test_upload_rejects_other_patient_and_unauthorized_user(self):
        with self.assertRaises(ReportOwnershipError):
            ingest_report("P7", "UP1")
        with self.assertRaises(PermissionError):
            ingest_report("P9", "UP1")
        self.assertFalse((self.dir / "reports").exists())

    def test_agent_explains_report_without_leaking_identifiers(self):
        report_ref = ingest_report("P8", "UP1")
        answer = self.agent.answer(
            f"{PATIENTS['P8']['id_card']} 帮我解释这份检查报告", report_ref=report_ref
        )
        self.assertIn("空腹血糖", answer)
        self.assertIn("高于参考范围", answer)
        self.assertIn("总胆固醇", answer)
        self.assertIn("以医生意见为准", answer)

        lines = self.log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertNotIn(PATIENTS["P8"]["id_card"], line)
            self.assertNotIn(FULL_ID, line)
            self.assertNotIn(PATIENTS["P8"]["phone"], line)
        first_request = json.loads(lines[0])["messages"]
        self.assertIn("[证件号已隐藏]", first_request[1]["content"])

    def test_model_cannot_override_patient_or_report_ref(self):
        report_ref = ingest_report("P8", "UP1")
        forced = {"tool": "read_report",
                  "arguments": {"patient_ref": "P7", "report_ref": "RPT-9999"}}
        original_send = self.agent.model.send

        def send(messages):
            response = original_send(messages)
            return forced if messages[-1]["role"] == "user" else response

        with patch.object(self.agent.model, "send", side_effect=send):
            answer = self.agent.answer(f"{PATIENTS['P8']['id_card']} {report_ref} 解释报告")
        self.assertIn("空腹血糖", answer)
        requests = [json.loads(line)["messages"] for line in self.log.read_text().splitlines()]
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[-1][-2]["tool_call"]["arguments"],
                         {"patient_ref": "P8", "report_ref": report_ref})

    def test_report_of_other_patient_and_unknown_ref_are_rejected(self):
        self.assertIn("请先", self.agent.answer("帮我解释一下检查报告"))
        report_ref = ingest_report("P8", "UP1")
        self.assertIn("不属于", self.agent.answer(f"{report_ref} 解释报告"))
        self.assertIn("空腹血糖", self.agent.answer(
            f"{PATIENTS['P8']['id_card']} 再解释一下这份报告"))
        self.assertIn("未找到", self.agent.answer(
            f"{PATIENTS['P8']['id_card']} RPT-9999 解释报告"))

    def test_login_switch_clears_pending_report_ref(self):
        report_ref = ingest_report("P8", "UP1")
        self.assertIn("空腹血糖", self.agent.answer(
            f"{PATIENTS['P8']['id_card']} {report_ref} 解释报告"))
        with patch.dict(SESSION, {"login_patient_ref": "P8", "authorized_refs": {"P8"}}):
            self.assertIn("请先", self.agent.answer("再解释一下这份报告"))

    def test_identifiers_inside_report_items_are_masked_before_model(self):
        report = {"patient_header": UPLOAD["patient_header"],
                  "items": [{"name": "送检备注", "value": "13800005678", "unit": "", "ref": ""}]}
        with patch.dict(REPORTS, {"UP2": report}):
            report_ref = ingest_report("P8", "UP2")
        self.agent.answer(f"{PATIENTS['P8']['id_card']} {report_ref} 解释报告")
        lines = self.log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertNotIn("13800005678", line)
        self.assertIn("138****5678", lines[-1])

    def test_report_tool_returns_only_business_items(self):
        report_ref = ingest_report("P8", "UP1")
        self.assertEqual(read_report("P8", report_ref),
                         {"report_ref": report_ref, "items": UPLOAD["items"]})
        with self.assertRaises(PermissionError):
            read_report("P7", report_ref)
        with self.assertRaises(PermissionError):
            read_report("P9", report_ref)
        with self.assertRaises(UnknownReportError):
            read_report("P8", "RPT-9999")


if __name__ == "__main__":
    unittest.main()
