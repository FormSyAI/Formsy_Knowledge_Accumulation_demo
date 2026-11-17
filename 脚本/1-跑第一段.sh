#!/usr/bin/env bash
# 第一段：把「裸 Agent」工作区交给一段全新开发会话（deepseek 通道，隔离 CODEX_HOME）
# 事件流 → 结果/第一段-开发会话事件.jsonl
set -u
DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_ISO="$DEMO_DIR/环境/codex-home"
WS="$DEMO_DIR/工作区-第一段"
TASK="$DEMO_DIR/材料/任务/第一段-任务.md"
OUT="$DEMO_DIR/结果"; mkdir -p "$OUT"
LOG="$OUT/第一段-开发会话事件.jsonl"
ERR="$OUT/第一段-stderr.log"

echo "工作区：$WS"
echo "起点　：$(git -C "$WS" log --oneline -1)"
echo "需求　：$TASK"
echo "模型　：tencent-cloud/deepseek-v4.1-flash（经 127.0.0.1:3425）"
echo "预计　：6–10 分钟"
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
echo "事件流：$LOG"
echo "stderr：$ERR"
exit "$rc"
