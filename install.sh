#!/data/data/com.termux/files/usr/bin/bash
# VoiceMap 一键安装
#   用法: sh install.sh [输入法包名]
#   不给包名时自动使用系统当前默认输入法
set -e

D="$(cd "$(dirname "$0")" && pwd)"
PY=/data/data/com.termux/files/usr/bin/python3
IME="${1:-}"

echo "== 1/4 安装触发 App"
su -c "pm install -r -g --user 0 $D/apk/voicemap.apk"

echo "== 2/4 安装 LSPosed 模块"
su -c "pm install -r -g --user 0 $D/apk/voicemap-ime.apk"

echo "== 3/4 在 LSPosed 里启用模块并设定作用域"
if [ -n "$IME" ]; then
  su -c "$PY $D/tools/lspd_enable.py $IME"
else
  su -c "$PY $D/tools/lspd_enable.py"
fi
IME_USED="$IME"
if [ -z "$IME_USED" ]; then
  IME_USED="$(su -c 'settings get secure default_input_method' | cut -d/ -f1)"
fi

echo "== 4/4 重启输入法进程（让模块被注入）"
sleep 1
P="$(su -c 'ps -A' | awk -v p="$IME_USED" '$0 ~ p {print $1; exit}')"
if [ -n "$P" ]; then
  su -c "kill $P" || true
  echo "   已结束输入法进程 pid=$P（下次输入时自动重启并加载模块）"
else
  echo "   输入法进程未运行，无需重启"
fi

echo
echo "完成（作用域=$IME_USED）。打开「语音按键」→ 首次进入会自动校准空格键位置，"
echo "然后按住蓝色按钮说话即可。"
echo
echo "换输入法/换手机："
echo "  python3 tools/lspd_enable.py --list          # 看本机有哪些输入法"
echo "  sh install.sh <输入法包名>                    # 重设作用域"
echo "  打开 App 后它会自动重新校准（不同分辨率会各自记一份坐标）"
