#!/usr/bin/env bash
# 演示前 30 秒检查：magpie 桥 / codex CLI / 隔离 CODEX_HOME / 模型目录 / 两个工作区
set -u
DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_ISO="$DEMO_DIR/环境/codex-home"
fail=0

echo "演示目录：$DEMO_DIR"
echo

if lsof -nP -iTCP:3425 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "✅ magpie 桥在监听 127.0.0.1:3425"
else
  echo "❌ magpie 桥没在 127.0.0.1:3425 监听 —— 没有它就没有 deepseek 通道"; fail=1
fi

if command -v codex >/dev/null 2>&1; then
  echo "✅ codex：$(codex --version 2>&1 | head -1)"
else
  echo "❌ 找不到 codex CLI"; fail=1
fi

if [ -f "$HOME_ISO/config.toml" ] && [ -f "$HOME_ISO/auth.json" ]; then
  echo "✅ 隔离 CODEX_HOME：$HOME_ISO"
else
  echo "❌ 隔离 CODEX_HOME 不完整（需要 config.toml 和 auth.json）"
  echo "   修：cp ~/.codex/auth.json \"$HOME_ISO/auth.json\" && chmod 600 \"$HOME_ISO/auth.json\""
  fail=1
fi

python3 - <<'PY'
import json, os
p = os.path.expanduser("~/.codex/magpie-desktop-models.json")
try:
    slugs = [m.get("slug") for m in json.load(open(p)).get("models", [])]
except Exception as exc:
    print(f"⚠️ 读不到模型目录 {p}：{exc}")
else:
    print("✅ 模型目录里有 tencent-cloud/deepseek-v4.1-flash"
          if "tencent-cloud/deepseek-v4.1-flash" in slugs
          else "❌ 模型目录里没有 tencent-cloud/deepseek-v4.1-flash")
PY

for ws in "工作区-第一段" "工作区-第二段"; do
  if [ -d "$DEMO_DIR/$ws/.git" ]; then
    echo "✅ ${ws}：$(git -C "$DEMO_DIR/$ws" log --oneline -1)"
  else
    echo "❌ $ws 缺 git 初始状态"; fail=1
  fi
done

echo
if [ "$fail" -eq 0 ]; then
  echo "环境就绪，可以开跑。"
else
  echo "有检查项没过，先解决这些再跑。"
fi
exit "$fail"
