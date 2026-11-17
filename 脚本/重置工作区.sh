#!/usr/bin/env bash
# 回到起点：把工作区回滚到各自的初始提交（连未跟踪文件一起清掉）
# 用法：重置工作区.sh 第一段 | 第二段 | all（默认 all）
set -u
DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

reset_one() {
  ws="$1"
  echo "回滚：$ws"
  git -C "$ws" reset --hard -q
  # -x：连 .gitignore 忽略掉的产物一起清（比如 AI 自己写的 local_reports/、evidence/、__pycache__/）
  git -C "$ws" clean -fdxq
  echo "  现在停在：$(git -C "$ws" log --oneline -1)"
}

case "${1:-all}" in
  第一段) reset_one "$DEMO_DIR/工作区-第一段" ;;
  第二段) reset_one "$DEMO_DIR/工作区-第二段" ;;
  all)
    reset_one "$DEMO_DIR/工作区-第一段"
    reset_one "$DEMO_DIR/工作区-第二段"
    ;;
  *) echo "用法：$0 第一段|第二段|all"; exit 2 ;;
esac
echo
echo "完成。第一段会回到「初始状态：裸 Agent」，第二段会回到「起点：预约查询已修复 + 报告解读任务」。"
