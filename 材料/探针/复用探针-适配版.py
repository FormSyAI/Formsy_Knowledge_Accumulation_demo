#!/usr/bin/env python3
"""适配探针（2026-11-17 第二段这次运行）：按它自己的真实入口验。

与原 `复用验证/探针脚本.py` 的差别：这一版把 OCR 从 `tools.report.LocalOCR` 注入
（原版是从构造器注入），其余判据一致——注入带全角证件号/手机号/姓名的报告抬头，
读**实际写出的模型请求**，检查禁传值是否出境。
"""
import json, os, sys, tempfile

WORK = os.path.abspath(sys.argv[1])
sys.path.insert(0, WORK)
os.chdir(WORK)

import tools.report

class HostileOCR:
    def read(self, report_ref):
        return {
            "patient_header": "姓名：张三丰(虚构)　证件号：３１０１０１１９８５１２０６１２３４　手机号：13900001234　性别：男",
            "items": [
                {"name": "空腹血糖", "value": "6.8", "unit": "mmol/L", "ref": "3.9-6.1"},
                {"name": "总胆固醇", "value": "5.2", "unit": "mmol/L", "ref": "<5.2"},
            ],
        }

tools.report.LocalOCR = HostileOCR

from model_client import ModelClient
from service import CustomerServiceAgent
from tools.report import upload_report

LOG = os.environ.get("PROBE_LOG", os.path.join(tempfile.gettempdir(), "report-probe-adapted.jsonl"))
if os.path.exists(LOG):
    os.remove(LOG)

agent = CustomerServiceAgent(model_client=ModelClient(log_path=LOG))
up = upload_report("P7", "R1")
reply = agent.answer("解释一下 R1 报告")
lines = [json.loads(l) for l in open(LOG, encoding="utf-8")] if os.path.exists(LOG) else []
payload = json.dumps([l["messages"] for l in lines], ensure_ascii=False)
sent_tool = None
for l in lines:
    for m in l["messages"]:
        if m.get("role") == "tool":
            sent_tool = m.get("content")
stored = os.path.join(WORK, "local_reports", "R1.json")
print(json.dumps({
    "请求次数": len(lines),
    "上传返回": up,
    "回复": str(reply)[:160],
    "原始报告是否留本机": os.path.exists(stored),
    "本机留存里是否有完整证件号": ("３１０１０１１９８５１２０６１２３４" in open(stored, encoding="utf-8").read()) if os.path.exists(stored) else None,
    "实际发给模型的 tool 内容": sent_tool,
    "泄露检查": {
        "全角证件号 ３１０１０１１９８５１２０６１２３４": "３１０１０１１９８５１２０６１２３４" in payload,
        "半角证件号 310101198512061234": "310101198512061234" in payload,
        "手机号 13900001234": "13900001234" in payload,
        "姓名 张三丰": "张三丰" in payload,
        "patient_header 字段名": "patient_header" in payload,
    },
}, ensure_ascii=False, indent=1))
