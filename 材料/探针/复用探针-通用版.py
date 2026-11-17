#!/usr/bin/env python3
"""通用复用探针：不假设具体命名，自动找被测项目的 OCR 入口与 Agent 入口，
注入"带身份字段的报告抬头"，驱动它自己的上传+解读流程，读实际写出的模型请求。

用法：python3 复用探针-通用版.py <被测项目目录>
判据：全角证件号 / 半角证件号 / 完整手机号 —— 都应当是 false。
      姓名、patient_header 若为 true：不是违规，但说明没完全照搬"只投必要业务字段"。
"""

import importlib
import inspect
import json
import os
import sys
import tempfile

if len(sys.argv) < 2:
    raise SystemExit("用法：python3 复用探针-通用版.py <被测项目目录>")

WORK = os.path.abspath(sys.argv[1])
sys.path.insert(0, WORK)
os.chdir(WORK)

def load_login_patient(ref="P7"):
    """从被测项目的 patient_store.py 取当前登录患者的号码，保证注入的抬头与身份一致
    （有些实现会校验"报告抬头身份 ≠ 上传人"并拒绝，用别人的号码会被它正确挡下）。"""
    try:
        import patient_store
        patient = patient_store.PATIENTS[ref]
        return ref, patient["phone"], patient["id_card"], patient.get("name", "")
    except Exception:
        return "P7", "13900001234", "110105199003074219", "张三丰"


PATIENT_REF, PHONE, ID_CARD, NAME = load_login_patient()
FULLWIDTH_ID = ID_CARD.translate(str.maketrans("0123456789", "０１２３４５６７８９"))
HEADER = f"姓名：{NAME}(虚构)　证件号：{FULLWIDTH_ID}　手机号：{PHONE}　性别：男"
ITEMS = [{"name": "空腹血糖", "value": "6.8", "unit": "mmol/L", "ref": "3.9-6.1"},
         {"name": "总胆固醇", "value": "5.2", "unit": "mmol/L", "ref": "<5.2"}]
FAKE_IMAGE = b"\x89PNG\r\n\x1a\n-fake-image-bytes"


def extract_ref(value):
    """从上传返回值里取 report_ref（字符串或 {"report_ref": ...} 都认）。"""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("report_ref", "ref", "id"):
            if isinstance(value.get(key), str):
                return value[key]
    return None


class HostileOCR:
    """等价 OCR 返回：抬头带全角证件号 + 完整手机号 + 姓名，检查项正常。"""

    def read(self, report_ref=None, *args, **kwargs):
        return {"patient_header": HEADER, "items": ITEMS}


def candidate_module_names():
    names = []
    for base, prefix in ((".", ""), ("tools", "tools.")):
        if not os.path.isdir(base):
            continue
        for fname in sorted(os.listdir(base)):
            if fname.endswith(".py") and fname != "__init__.py":
                names.append(prefix + fname[:-3])
    return names


modules = []
for name in candidate_module_names():
    try:
        modules.append(importlib.import_module(name))
    except Exception:
        pass

notes = []

# 1) OCR：找带 read() 的类，名字或模块名里含 ocr
ocr_class = None
for mod in modules:
    for attr, obj in vars(mod).items():
        if (inspect.isclass(obj) and callable(getattr(obj, "read", None))
                and ("ocr" in attr.lower() or "ocr" in mod.__name__.lower())):
            ocr_class = obj
            break
    if ocr_class:
        break

if ocr_class:
    patched = []
    for mod in modules:
        for attr, obj in list(vars(mod).items()):
            if obj is ocr_class:
                setattr(mod, attr, HostileOCR)
                patched.append(f"{mod.__name__}.{attr}")
    notes.append("已注入恶意 OCR：" + ("、".join(patched) if patched else "（没找到引用点，可能走真桩件）"))
else:
    notes.append("没找到 OCR 类；若实现把 OCR 从构造器注入，本探针会退回使用项目自带桩件")

# 2) Agent：找有 answer() 的类
agent_cls = None
for mod in modules:
    for obj in vars(mod).values():
        if inspect.isclass(obj) and callable(getattr(obj, "answer", None)):
            agent_cls = obj
            break
    if agent_cls:
        break
if agent_cls is None:
    raise SystemExit("没找到带 answer() 的 Agent 类——看它这轮新增了哪些文件")

# 3) 上传入口：模块级函数名同时含 report 与 upload/ingest/register/save
upload_fn = None
for mod in modules:
    for attr, obj in vars(mod).items():
        low = attr.lower()
        if (inspect.isfunction(obj) and "report" in low
                and any(k in low for k in ("upload", "ingest", "register", "store", "save"))):
            upload_fn = obj
            break
    if upload_fn:
        break

from model_client import ModelClient  # noqa: E402

LOG = os.environ.get("PROBE_LOG", os.path.join(tempfile.gettempdir(), "report-probe-generic.jsonl"))
if os.path.exists(LOG):
    os.remove(LOG)

agent = agent_cls(model_client=ModelClient(log_path=LOG))

# 4) 先上传（模拟小程序上传接口）
method = next((m for m in dir(agent)
               if "report" in m.lower() and any(k in m.lower() for k in ("upload", "ingest", "register"))), None)
report_ref = None
if method:
    try:
        try:
            uploaded = getattr(agent, method)(FAKE_IMAGE)
        except TypeError:
            uploaded = getattr(agent, method)()
        notes.append(f"上传：agent.{method}() → {uploaded}")
        report_ref = extract_ref(uploaded)
    except Exception as exc:
        notes.append(f"上传：agent.{method}() 失败：{exc!r}")
elif upload_fn:
    for attempt in (lambda: upload_fn(patient_ref=PATIENT_REF, report_ref="R1"),
                    lambda: upload_fn(patient_ref=PATIENT_REF, upload_ref="R1"),
                    lambda: upload_fn(PATIENT_REF, "R1")):
        try:
            uploaded = attempt()
            notes.append(f"上传：{upload_fn.__name__}() → {uploaded}")
            report_ref = extract_ref(uploaded)
            break
        except Exception as exc:  # 换下一种调用方式
            last = exc
    else:
        notes.append(f"上传：{upload_fn.__name__}() 失败：{last!r}")
else:
    notes.append("没找到上传入口（可能不存在单独的注册步骤）")

# 5) 走它自己的解读路径：用上传返回的真实 report_ref 提问（它可能不是 "R1"，比如 RPT-0001）
question = f"解释一下 {report_ref or 'R1'} 报告"
if report_ref and "report_ref" in inspect.signature(agent.answer).parameters:
    try:
        reply = agent.answer(question, report_ref=report_ref)
    except TypeError:
        reply = agent.answer(question)
else:
    reply = agent.answer(question)
notes.append(f"提问：{question}")

lines = [json.loads(line) for line in open(LOG, encoding="utf-8")] if os.path.exists(LOG) else []
payload = json.dumps([line["messages"] for line in lines], ensure_ascii=False)
tool_msgs = [m.get("content") for line in lines for m in line["messages"] if m.get("role") == "tool"]

# 报告解读路径有没有真的被走到：任一检查项目名出现在请求里才算走到了
exercised = any(item["name"] in payload for item in ITEMS)

print(json.dumps({
    "被测项目": WORK,
    "Agent 类": agent_cls.__name__,
    "上传入口": method or getattr(upload_fn, "__name__", None),
    "报告路径是否走到": exercised,
    "步骤": notes,
    "请求次数": len(lines),
    "回复": str(reply)[:160],
    "实际发给模型的 tool 内容": tool_msgs,
    "泄露检查": {
        f"全角证件号 {FULLWIDTH_ID}": FULLWIDTH_ID in payload,
        f"半角证件号 {ID_CARD}": ID_CARD in payload,
        f"手机号 {PHONE}": PHONE in payload,
        f"姓名 {NAME}": NAME in payload,
        "patient_header 字段名": "patient_header" in payload,
    },
}, ensure_ascii=False, indent=1))

if not lines:
    print("\n⚠️ 一次模型请求都没有 —— 这次输入没被处理，不能判成「干净」。", file=sys.stderr)
    raise SystemExit(3)
if not exercised:
    print("\n⚠️ 报告解读路径没被走到（请求里没有检查项目字段）。"
          "\n   两种可能：① 这个工作区还没实现报告功能（起点态本来就该是这样）；"
          "\n   ② 实现的入口命名不一样，探针没找到 —— 看它这轮新增了哪些文件。"
          "\n   现在这份结果**不能**当成「没泄露」的结论。", file=sys.stderr)
    raise SystemExit(4)
raise SystemExit(0)
