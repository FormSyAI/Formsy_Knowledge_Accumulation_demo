#!/usr/bin/env python3
"""复用验证探针：把带身份字段的等价 OCR 返回注入被测项目，检查实际模型请求里是否出现禁传值。

用法：python3 探针脚本.py <被测项目目录>
"""
import json, os, sys, tempfile

if len(sys.argv) < 2:
    raise SystemExit("用法：python3 探针脚本.py <被测项目目录>")
WORK = os.path.abspath(sys.argv[1])
sys.path.insert(0, WORK)
os.chdir(WORK)
from model_client import ModelClient
from service import CustomerServiceAgent

class HostileOCR:
    """等价 OCR 返回：抬头带全角证件号 + 手机号 + 姓名，检查项正常。"""
    def read(self, report_ref):
        return {
            "patient_header": "姓名：张三丰(虚构)　证件号：３１０１０１１９８５１２０６１２３４　手机号：13900001234　性别：男",
            "items": [
                {"name": "空腹血糖", "value": "6.8", "unit": "mmol/L", "ref": "3.9-6.1"},
                {"name": "总胆固醇", "value": "5.2", "unit": "mmol/L", "ref": "<5.2"},
            ],
        }

LOG = os.environ.get("PROBE_LOG", os.path.join(tempfile.gettempdir(), "report-probe-requests.jsonl"))
REPDIR = os.environ.get("PROBE_REPORTS", os.path.join(tempfile.gettempdir(), "report-probe-reports"))
for p in (LOG,):
    if os.path.exists(p): os.remove(p)
agent = CustomerServiceAgent(model_client=ModelClient(log_path=LOG), report_ocr=HostileOCR(), report_dir=REPDIR)
res = agent.upload_report(b"\x89PNG\r\n\x1a\n-fake-image-bytes")
lines = [json.loads(l) for l in open(LOG, encoding="utf-8")] if os.path.exists(LOG) else []
payload = json.dumps([l["messages"] for l in lines], ensure_ascii=False)
ref = res.get("report_ref")
sent_tool = None
for l in lines:
    for m in l["messages"]:
        if m.get("role") == "tool":
            sent_tool = m.get("content")
print(json.dumps({
    "请求次数": len(lines),
    "返回字段": sorted(res.keys()),
    "explanation": (res.get("explanation") or "")[:140],
    "原图是否留在本机": bool(ref) and os.path.exists(os.path.join(REPDIR, ref)),
    "实际发给模型的 tool 内容": sent_tool,
    "泄露检查": {
        "全角证件号 ３１０１０１１９８５１２０６１２３４": "３１０１０１１９８５１２０６１２３４" in payload,
        "半角证件号 310101198512061234": "310101198512061234" in payload,
        "手机号 13900001234": "13900001234" in payload,
        "姓名 张三丰": "张三丰" in payload,
        "patient_header 字段名": "patient_header" in payload,
    },
}, ensure_ascii=False, indent=1))
