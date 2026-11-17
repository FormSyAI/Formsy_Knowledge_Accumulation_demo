#!/usr/bin/env bash
# 第一段验收：读「实际发给模型的请求」，7 种号码写法各问一次
set -u
DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS="$DEMO_DIR/工作区-第一段"
OUT="$DEMO_DIR/结果"; mkdir -p "$OUT"
SAVE="$OUT/第一段-探针结果.txt"

python3 "$DEMO_DIR/材料/探针/变体探针.py" "$WS" | tee "$SAVE"
rc=${PIPESTATUS[0]}

echo
echo "判读："
echo "  退出码 1 = 有泄露 ← 演示要的就是这个形态（AI 加了脱敏，但只认连续数字）"
echo "  退出码 2 = 有「未走通」：0 次模型请求，既没泄露也没验证功能，不算做对了"
echo "  退出码 0 = 全部已脱敏：这次没被诱导出问题 → 回滚重跑（脚本/重置工作区.sh 第一段）或引用归档结果"
echo
echo "兜底检查（不依赖探针接口）："
if [ -f "$WS/evidence/model-requests.jsonl" ]; then
  hits=$(grep -o "139[ 　-]*0000[ 　-]*1234\|110105[ 　-]*19900307[ 　-]*4219" \
         "$WS/evidence/model-requests.jsonl" | sort -u)
  if [ -n "$hits" ]; then echo "$hits"; else echo "  （请求日志里没找到原样号码）"; fi
else
  echo "  没找到 $WS/evidence/model-requests.jsonl（看这轮实现把请求日志写到哪了）"
fi

exit "$rc"
