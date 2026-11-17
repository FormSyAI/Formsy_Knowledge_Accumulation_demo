#!/usr/bin/env python3
"""变体矩阵探针：检查同一患者身份的不同写法是否会被送进模型请求。

用法：python3 变体探针.py <客服Agent项目目录>
"""
import json, os, sys, tempfile

REPO = sys.argv[1]
sys.path.insert(0, REPO)
from model_client import ModelClient          # noqa: E402
from service import CustomerServiceAgent      # noqa: E402

PHONE = "13900001234"
ID_CARD = "110105199003074219"
VARIANTS = [
    ("手机号-连续",        f"{PHONE} 的预约"),
    ("手机号-空格分隔",     "139 0000 1234 的预约"),
    ("手机号-短横分隔",     "139-0000-1234 的预约"),
    ("手机号-不规则空格",   "1390000 1234 的预约"),
    ("手机号-全角",        "１３９００００１２３４ 的预约"),
    ("证件号-连续",        f"{ID_CARD} 的预约"),
    ("证件号-空格分隔",     "110105 19900307 4219 的预约"),
]

print(f"被测项目：{REPO}\n")
print(f"{'写法':<20}{'模型请求数':>8}  原样原文进入请求")
leaked, not_run = [], []
for label, text in VARIANTS:
    log = tempfile.mktemp(suffix=".jsonl")
    agent = CustomerServiceAgent(model_client=ModelClient(log_path=log))
    agent.answer(text)
    reqs = [json.loads(l) for l in open(log, encoding="utf-8")] if os.path.exists(log) else []
    hit = any(text in json.dumps(r, ensure_ascii=False) for r in reqs)
    # 去掉尾部的"的预约"再比一次，排除只匹配到问句整体的可能
    core = text[:-3].strip()
    hit_core = any(core in json.dumps(r, ensure_ascii=False) for r in reqs)
    if hit or hit_core:
        mark = "泄露"
        leaked.append(label)
    elif len(reqs) == 0:
        # 一次模型请求都没发：不能算"已脱敏"——很可能是压根没走通这条输入
        mark = "未走通"
        not_run.append(label)
    else:
        mark = "已脱敏"
    print(f"{label:<20}{len(reqs):>8}  {mark}")
    if os.path.exists(log):
        os.remove(log)

print()
print("泄露的写法：" + ("、".join(leaked) if leaked else "无"))
if not_run:
    print("未走通的写法（0 次模型请求，不能当成\"已脱敏\"）：" + "、".join(not_run))
print()
print("判读：泄露=禁传值原样出境；未走通=这次输入没被处理，"
      "既没泄露也没验证功能，必须单独看回复是否合理；已脱敏=发了请求且原文被处理掉。")
sys.exit(1 if leaked else (2 if not_run else 0))
