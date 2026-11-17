#!/usr/bin/env bash
# 一键把仓库展开成可跑的演示环境：
#   · 工作区-第一段 = 裸 Agent（git 已初始化，停在「初始状态：裸 Agent」）
#   · 工作区-第二段 = 预约查询已修复 + OCR 桩件 + 召回结果 + 任务（三个提交）
#   · 环境/codex-home = 隔离 CODEX_HOME（config 按当前路径生成，凭据从 ~/.codex/auth.json 拷）
# 用法：bash 部署.sh（在仓库根目录执行；重复执行不会覆盖已有工作区）
set -u
DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DEMO_DIR"

if [ -d 工作区-第一段 ] || [ -d 工作区-第二段 ]; then
  echo "工作区已存在：$(ls -d 工作区-* 2>/dev/null | tr '\n' ' ')"
  echo "要重建就先删掉它们；只想回到起点用：bash 脚本/重置工作区.sh all"
  exit 1
fi

init_repo() {
  ws="$1"; msg="$2"
  git -C "$ws" init -q
  git -C "$ws" config user.email "demo@local"
  git -C "$ws" config user.name "demo"
  git -C "$ws" add -A
  git -C "$ws" commit -qm "$msg"
}

echo "▶ 展开 工作区-第一段（裸 Agent）"
cp -R 起始状态 工作区-第一段
python3 材料/探针/演示日期准备.py 工作区-第一段 >/dev/null
init_repo 工作区-第一段 "初始状态：裸 Agent"

echo "▶ 展开 工作区-第二段（预约查询已修复 + 报告解读任务）"
cp -R 起始状态 工作区-第二段
init_repo 工作区-第二段 "初始状态：裸 Agent"
git -C 工作区-第二段 apply "$DEMO_DIR/材料/补丁/预约查询-实现与修复.patch"
git -C 工作区-第二段 add -A
git -C 工作区-第二段 commit -qm "预约查询（已修复）"
cp 材料/知识/起始文件-report_ocr.py 工作区-第二段/report_ocr.py
cp 材料/知识/项目知识召回.json 工作区-第二段/
cp 材料/任务/第二段-任务.md 工作区-第二段/任务.md
git -C 工作区-第二段 add -A
git -C 工作区-第二段 commit -qm "起点：预约查询已修复 + 报告解读任务"

echo "▶ 生成隔离 CODEX_HOME"
bash 环境/重建隔离home.sh | tail -2

echo
echo "部署完成："
for ws in 工作区-第一段 工作区-第二段; do
  echo "  · ${ws}：$(git -C "$ws" log --oneline -1)"
done
echo
echo "接下来："
echo "  bash 环境/检查环境.sh     # 自检（magpie 桥 / codex CLI / home / 模型 / 两个工作区）"
echo "  open 复现流程.md          # 照着走"
echo "  bash 脚本/跑完整流程.sh    # 或者一条龙（两段真实模型会话，约 12–19 分钟）"
