#!/usr/bin/env bash
# 第二段：在「预约查询已修复 + 召回结果已就位」的起点上，做报告解读（换模块验证复用）
# 事件流 → 结果/第二段-开发会话事件.jsonl
set -u
DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_ISO="$DEMO_DIR/环境/codex-home"
WS="$DEMO_DIR/工作区-第二段"
TASK="$DEMO_DIR/材料/任务/第二段-任务.md"
OUT="$DEMO_DIR/结果"; mkdir -p "$OUT"
LOG="$OUT/第二段-开发会话事件.jsonl"
ERR="$OUT/第二段-stderr.log"

echo "工作区：$WS"
echo "起点　：$(git -C "$WS" log --oneline -1)"
echo "需求　：${TASK}（里面写明「请先读 项目知识召回.json」）"
echo "模型　：tencent-cloud/deepseek-v4.1-flash（经 127.0.0.1:3425）"
echo "预计　：5–9 分钟"
echo

cd "$WS" || exit 1
CODEX_HOME="$HOME_ISO" codex exec --json -C "$WS" -s workspace-write \
  -m tencent-cloud/deepseek-v4.1-flash "$(cat "$TASK")" > "$LOG" 2> "$ERR" < /dev/null
rc=$?

echo "退出码：${rc}　事件数：$(wc -l < "$LOG" | tr -d ' ')"
echo
echo "它改了什么："
git -C "$WS" status --porcelain
echo
echo "第一件事是不是读了召回结果（下面应该能看到 cat 项目知识召回.json）："
grep -o "cat 项目知识召回.json" "$LOG" | head -1 || echo "  （没在事件流里看到；再翻 ${LOG}）"
echo
echo "事件流：$LOG"
exit "$rc"
