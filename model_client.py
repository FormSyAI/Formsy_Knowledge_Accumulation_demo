"""模型客户端：本机演示写请求日志，不访问外网。"""

import json
import os
import re
from datetime import date, timedelta

EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence")
REQUEST_LOG = os.path.join(EVIDENCE_DIR, "model-requests.jsonl")


class ModelClient:
    def __init__(self, log_path=None):
        self.log_path = log_path or REQUEST_LOG

    def send(self, messages):
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"event": "model_request", "messages": messages},
                                ensure_ascii=False) + "\n")
        if messages[-1]["role"] == "user":
            return self._choose_tool(messages)
        if messages[-1]["name"] == "list_appointments":
            return self._format_appointments(messages[-1]["content"], messages[1]["content"])
        return "已为您查询。"

    def _choose_tool(self, messages):
        """模拟本机演示所需的预约意图和参数。"""
        user_text = messages[-1]["content"]
        ordinal = re.search(r"第([0-9]+|[一二三四五六七八九十两])条", user_text)
        if ordinal and ("科室" in user_text or "预约" in user_text):
            number = ordinal[1]
            index = int(number) if number.isascii() else "〇一二三四五六七八九十".index(
                number.replace("两", "二")
            )
            return {"tool": "list_appointments", "arguments": {"index": index}}

        if "预约" not in user_text and "挂号" not in user_text:
            return {"tool": "patient_profile", "arguments": {}}

        arguments = {}
        explicit_date = re.search(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", user_text)
        relative_date = re.search(r"今天|明天|后天|昨天", user_text)
        if explicit_date:
            arguments["date"] = explicit_date[0]
        elif relative_date:
            today = date.fromisoformat(re.search(
                r"今天是 ([0-9]{4}-[0-9]{2}-[0-9]{2})", messages[0]["content"]
            )[1])
            offset = {"今天": 0, "明天": 1, "后天": 2, "昨天": -1}[relative_date[0]]
            arguments["date"] = (today + timedelta(days=offset)).isoformat()

        department = re.search(r"口腔科|内科", user_text)
        if department:
            arguments["department"] = department[0]
        return {"tool": "list_appointments", "arguments": arguments}

    def _format_appointments(self, result, user_text):
        if "appointment" in result:
            row = result["appointment"]
            if "科室" in user_text:
                return f"第{result['index']}条预约的科室是{row['department']}。"
            return self._format_row(result["index"], row)
        return "\n".join(self._format_row(index, row)
                         for index, row in enumerate(result["appointments"], 1)) or "未查到符合条件的预约。"

    def _format_row(self, index, row):
        return f"{index}. {row['date']} {row['time']} {row['department']}（{row['status']}）"
