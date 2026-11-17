#!/usr/bin/env python3
"""把演示工作副本里的预约/账单日期改写成"今天 / 明天"。

用法：
    python3 演示日期准备.py <工作副本目录> [--today YYYY-MM-DD]

工作副本应当是从 `起始仓库/` 复制出来的（不要直接在本目录的 `起始仓库/` 上跑）。

- 确定性地改写 `hospital_api.py` 里 5 处 `"date": "..."`：
  A12=今天、A13=明天、A21=今天、P7 两张账单=今天-7 天。
  因为不依赖现有取值，**重复执行结果相同**（幂等）。
- 只写工作副本；其它文件与归档材料一律不动。
- `--today` 仅用于预演/自测：假装今天是别的日期。
"""

import os
import re
import sys
from datetime import date, datetime, timedelta

TARGET_FILE = "hospital_api.py"
DATE_FIELD = re.compile(r'"date":\s*"(\d{4}-\d{2}-\d{2})"')
# 与 hospital_api.py 里出现的顺序一致：A12、A13、A21、账单 1、账单 2
TARGETS = [("今天", 0), ("明天", 1), ("今天", 0), ("今天-7 天", -7), ("今天-7 天", -7)]


def main():
    argv = sys.argv[1:]
    today = date.today()
    if "--today" in argv:
        i = argv.index("--today")
        try:
            today = datetime.strptime(argv[i + 1], "%Y-%m-%d").date()
        except (IndexError, ValueError):
            print("--today 需要一个 YYYY-MM-DD 形式的日期")
            return 2
        del argv[i:i + 2]
    if len(argv) != 1:
        print(__doc__.strip())
        return 2

    target = os.path.abspath(argv[0])
    path = os.path.join(target, TARGET_FILE)
    if not os.path.isfile(path):
        print(f"没找到 {TARGET_FILE}：{path}\n（这份副本是从 `起始仓库/` 复制出来的吗？）")
        return 2

    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    matches = list(DATE_FIELD.finditer(text))
    if len(matches) != len(TARGETS):
        print(f'{TARGET_FILE} 里找到 {len(matches)} 处 "date"，预期 {len(TARGETS)} 处——'
              "夹具结构变了，请先核对，脚本不做任何写入。")
        return 1

    pieces, cursor, changes = [], 0, []
    for match, (label, offset) in zip(matches, TARGETS):
        new_date = (today + timedelta(days=offset)).isoformat()
        pieces.append(text[cursor:match.start(1)])
        pieces.append(new_date)
        cursor = match.end(1)
        changes.append((match.group(1), new_date, label))
    pieces.append(text[cursor:])
    new_text = "".join(pieces)

    print(f"按演示日 {today.isoformat()} 改写 {target}/{TARGET_FILE}：")
    for old, new, label in changes:
        print(f"  {old} → {new}   （{label}）")

    if new_text == text:
        print("\n内容无变化（这份副本已经是目标日期）。")
        return 0

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new_text)
    print("\n完成。接下来按 README 步骤 2 继续：git init 并提交起始状态。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
