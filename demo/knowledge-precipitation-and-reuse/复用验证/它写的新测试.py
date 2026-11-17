import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from model_client import ModelClient
from report_ocr import LocalOCR
from service import CustomerServiceAgent


class ReportTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(directory.cleanup)
        self.report_dir = Path(directory.name) / "reports"
        self.log = Path(directory.name) / "requests.jsonl"
        self.ocr = Mock(spec=LocalOCR)
        self.agent = CustomerServiceAgent(
            ModelClient(self.log), report_ocr=self.ocr, report_dir=self.report_dir
        )
        self.image = b"\x89PNG\r\n\x1a\nreport bytes"

    def test_upload_preserves_image_and_sends_only_redacted_items(self):
        phone = "１３9－0000　１２３４"
        card = "３１０１０１１９８５１２０６１２３４"

        def read(report_ref):
            self.assertEqual((self.report_dir / report_ref).read_bytes(), self.image)
            report = LocalOCR().read("R1")
            return {
                "patient_header": report["patient_header"],
                "items": [*report["items"], {
                    "name": "识别样例 " + phone,
                    "value": card,
                    "phone": "13800005678",
                }],
            }

        self.ocr.read.side_effect = read
        result = self.agent.upload_report(self.image)
        self.ocr.read.assert_called_once_with(result["report_ref"])
        self.assertIn("空腹时血液里的葡萄糖水平", result["explanation"])
        self.assertIn("6.8 mmol/L", result["explanation"])
        self.assertIn("3.9-6.1", result["explanation"])

        payload = self.log.read_text(encoding="utf-8")
        messages = json.loads(payload)["messages"]
        self.assertEqual(messages[-1]["content"][-1], {
            "name": "识别样例 139****1234",
            "value": "[证件号已隐藏]",
        })
        for private_value in (phone, card, "张三丰", "13800005678", result["report_ref"], "report bytes"):
            self.assertNotIn(private_value, payload)
            self.assertNotIn(private_value, result["explanation"])

    def test_model_response_is_redacted(self):
        self.ocr.read.return_value = LocalOCR().read("R1")
        self.agent.model = Mock()
        self.agent.model.send.return_value = "139-0000-1234 / 110105199003074219"
        result = self.agent.upload_report(self.image)
        self.assertEqual(result["explanation"], "139****1234 / [证件号已隐藏]")

    def test_failed_and_empty_ocr_keep_original_without_model_call(self):
        self.ocr.read.side_effect = [OSError("read failed"), {"items": []}]
        refs = set()
        for _ in range(2):
            result = self.agent.upload_report(self.image)
            refs.add(result["report_ref"])
            self.assertIn("未能识别", result["explanation"])
            self.assertEqual((self.report_dir / result["report_ref"]).read_bytes(), self.image)
        self.assertEqual(len(refs), 2)
        self.assertFalse(self.log.exists())

    def test_model_failure_keeps_original(self):
        self.ocr.read.return_value = LocalOCR().read("R1")
        self.agent.model = Mock()
        self.agent.model.send.side_effect = OSError("model unavailable")
        result = self.agent.upload_report(self.image)
        self.assertIn("暂时无法生成解释", result["explanation"])
        self.assertEqual((self.report_dir / result["report_ref"]).read_bytes(), self.image)

    def test_rejected_upload_does_not_save_or_process_image(self):
        self.assertIsNone(self.agent.upload_report(b"")["report_ref"])
        with patch.dict("service.SESSION", login_patient_ref="unknown"):
            self.assertIsNone(self.agent.upload_report(self.image)["report_ref"])
        self.assertFalse(self.report_dir.exists())
        self.ocr.read.assert_not_called()
        self.assertFalse(self.log.exists())
