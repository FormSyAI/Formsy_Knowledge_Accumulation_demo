#!/usr/bin/env bash
# 把隔离 CODEX_HOME 清回「出厂状态」：只剩 config.toml + auth.json
# 用途：每演完一轮想再演一次时跑一遍，保证下一段会话是全新的（也没有旧会话可被误 resume）
set -u
DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_ISO="$DEMO_DIR/环境/codex-home"

mkdir -p "$HOME_ISO"

echo "清空：$HOME_ISO"
python3 - "$HOME_ISO" <<'PY'
import os, shutil, sys
home = sys.argv[1]
keep = {"config.toml", "auth.json"}
for name in os.listdir(home):
    if name in keep:
        continue
    path = os.path.join(home, name)
    shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
    print("  删掉：", name)
PY

cat > "$HOME_ISO/config.toml" <<TOML
# 隔离的 CODEX_HOME：全新会话，不带本案例任何历史
model = "tencent-cloud/deepseek-v4.1-flash"
openai_base_url = "http://127.0.0.1:3425/backend-api/codex"
model_catalog_json = "/Users/lili/.codex/magpie-desktop-models.json"

[projects."$DEMO_DIR/工作区-第一段"]
trust_level = "trusted"

[projects."$DEMO_DIR/工作区-第二段"]
trust_level = "trusted"
TOML

if [ -f ~/.codex/auth.json ]; then
  cp ~/.codex/auth.json "$HOME_ISO/auth.json"
  chmod 600 "$HOME_ISO/auth.json"
  echo "凭据已刷新：auth.json（权限 600）"
else
  echo "⚠️ 找不到 ~/.codex/auth.json —— 请先在本机登录 codex，再重跑本脚本"
  exit 1
fi

echo
echo "完成。现在是：$(ls "$HOME_ISO" | tr '\n' ' ')"
