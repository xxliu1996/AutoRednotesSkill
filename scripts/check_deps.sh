#!/usr/bin/env bash
# 幂等的依赖安装脚本 —— 建本 skill 自己的 .venv，与其他 skill 隔离。
# 参照 article-to-narration-video/scripts/check_deps.sh 的模式。
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$SKILL_DIR/.venv"

if [ ! -d "$VENV" ]; then
  echo "==> 创建虚拟环境 $VENV"
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "==> 安装 Python 依赖"
pip install -q --upgrade pip
pip install -q -r "$SKILL_DIR/requirements.txt"

# Playwright 的 chromium 装在 ~/Library/Caches/ms-playwright（全局共享），
# 若其他 skill 已装过这一步是快速 no-op。
echo "==> 确认 chromium"
python -m playwright install chromium

# 渲染模板 @import 了 Google Fonts 的 Noto Sans SC，无网络时会回退到本地字体。
if ! fc-list 2>/dev/null | grep -qi "PingFang\|Heiti\|Noto Sans SC"; then
  echo "提示: 未探测到中文字体，中文可能渲染为方块（macOS 自带 PingFang SC，通常无需处理）"
fi

echo "==> 依赖就绪"
