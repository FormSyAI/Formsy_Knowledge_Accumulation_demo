"""隐私与合规：完整手机号、证件号不进入模型请求。"""

import os
import tempfile
import unittest

from hospital_api import HospitalAPI
from model_client import ModelClient
from privacy import find_identifiers, mask_id_card, mask_phone, mask_text
from service import CustomerServiceAgent
from tools.medications import list_medications
from tools.patient_profile import patient_profile

PHONE = "13900001234"
ID_CARD = "110105199003074219"


class MaskingTests(unittest.TestCase):
    def test_mask_phone_and_id_card(self):
        self.assertEqual("139****1234", mask_phone(PHONE))
        self.assertEqual("110105********4219", mask_id_card(ID_CARD))

    def test_mask_text_and_find_identifiers(self):
        text = f"帮我查 {PHONE} 和 {ID_CARD} 的预约"
        self.assertEqual([PHONE, ID_CARD], find_identifiers(text))
        masked = mask_text(text)
        self.assertNotIn(PHONE, masked)
        self.assertNotIn(ID_CARD, masked)
        self.assertIn("139****1234", masked)
        self.assertIn("110105********4219", masked)

    def test_tools_mask_patient_records(self):
        result = patient_profile("P7")
        self.assertEqual("139****1234", result["patient"]["phone"])
        self.assertEqual("110105********4219", result["patient"]["id_card"])
        self.assertEqual(2, len(list_medications("P7")["medications"]))
        self.assertEqual("139****1234", list_medications("P7")["patient"]["phone"])
        # 院内接口本身保留完整数据（工作站风格），脱敏发生在工具适配层
        self.assertEqual(PHONE, HospitalAPI().patient_profile(7001)["patient"]["phone"])


class ModelRequestPrivacyTests(unittest.TestCase):
    def test_model_log_contains_no_full_identifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "model-requests.jsonl")
            agent = CustomerServiceAgent(model_client=ModelClient(log_path=log_path))
            agent.answer(f"{PHONE}，明天有什么预约？")
            agent.answer("刚才那个人第二条是哪个科室？")
            with open(log_path, encoding="utf-8") as fh:
                logged = fh.read()

        self.assertNotIn(PHONE, logged)
        self.assertNotIn(ID_CARD, logged)
        self.assertIn("139****1234", logged)
        self.assertIn("110105********4219", logged)


if __name__ == "__main__":
    unittest.main()
