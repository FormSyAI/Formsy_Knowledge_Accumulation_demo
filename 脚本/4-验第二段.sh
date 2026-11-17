#!/usr/bin/env bash
# 第二段验收：注入带全角证件号 / 手机号 / 姓名的报告抬头，读「实际发给模型的请求」
# 三个探针依次尝试：通用版（自动找入口）→ 适配版 → 原始版；都不行才走兜底检查。
set -u
DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS="$DEMO_DIR/工作区-第二段"
P="$DEMO_DIR/材料/探针"
OUT="$DEMO_DIR/结果"; mkdir -p "$OUT"
PROBE_LOG="$OUT/第二段-探针请求日志.jsonl"
SAVE="$OUT/第二段-探针结果.json"
ERR="$OUT/第二段-探针-stderr.log"

export PROBE_LOG
: > "$ERR"
rc=1
used=""

for pair in "通用版:${P}/复用探针-通用版.py" \
            "适配版:${P}/复用探针-适配版.py" \
            "原始版:${P}/复用探针-原始版.py"; do
  label="${pair%%:*}"; script="${pair#*:}"
  echo "▸ 试 ${label} 探针…"
  python3 "$script" "$WS" > "$SAVE" 2>> "$ERR"
  rc=$?
  if [ "$rc" -eq 0 ]; then used="$label"; break; fi
  if [ "$rc" -eq 4 ]; then
    echo "  ${label}：报告解读路径没被走到（工作区可能还没实现报告功能，或入口命名不同）"
    break
  fi
  echo "  ${label} 没跑通（退出码 ${rc}），换下一个"
done

if [ "$rc" -ne 0 ]; then
  echo
  sed -n '1,8p' "$ERR" | grep -v "^$" | head -8
  echo
  echo "三个探针都没给出结论 —— 别把它当成「没泄露」。兜底检查："
  echo "  1) 看这轮新增了哪些文件：git -C \"$WS\" status --porcelain"
  echo "  2) 用它自己的入口跑一次上传+解读，然后："
  echo "     grep -o \"３１０１０１１９８５１２０６１２３４\\|310101198512061234\\|13900001234\" \"$PROBE_LOG\" | sort -u"
  echo "     （没有输出 = 禁传值确实没进模型请求）"
  exit "$rc"
fi

echo "✅ ${used} 探针跑通"
echo
cat "$SAVE"
echo
echo "判读："
echo "  · 全角证件号 / 半角证件号 / 完整手机号 → 必须是 false（本项目禁传项）"
echo "  · 姓名 / patient_header 若为 true：不是违规；它也可能来自 Agent 的系统提示（当前就诊人），"
echo "    不一定来自报告工具 —— 看上面「实际发给模型的 tool 内容」再下结论"
echo
echo "请求日志留档：$PROBE_LOG"
