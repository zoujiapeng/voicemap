#!/usr/bin/env python3
"""
在 LSPosed 数据库里启用 VoiceMap 模块，并把作用域设成「本机当前的输入法」。

用法（root）：
    python3 lspd_enable.py                 # 自动取系统当前默认输入法作为作用域
    python3 lspd_enable.py com.xxx.ime     # 手动指定输入法包名
    python3 lspd_enable.py --list          # 只列出本机输入法
"""
import sqlite3
import subprocess
import sys

DB = '/data/adb/lspd/config/modules_config.db'
MODULE = 'com.pj.voicemap.ime'


def sh(*cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ''


def ime_list():
    out = sh('ime', 'list', '-a', '-s')
    return [l.strip() for l in out.splitlines() if '.' in l]


def default_ime_pkg():
    cur = sh('settings', 'get', 'secure', 'default_input_method')
    if '/' in cur:
        return cur.split('/')[0]
    enabled = sh('settings', 'get', 'secure', 'enabled_input_methods')
    for part in enabled.split(':'):
        if '/' in part:
            return part.split('/')[0]
    return 'com.sohu.inputmethod.sogouoem'


def main():
    args = [a for a in sys.argv[1:] if a]
    if '--list' in args:
        print('本机输入法：')
        for l in ime_list():
            print('  ', l)
        return
    ime = args[0] if args else default_ime_pkg()
    apk = sh('pm', 'path', MODULE)
    apk = apk.split(':', 1)[1] if ':' in apk else apk
    if not apk:
        print('模块未安装：', MODULE)
        sys.exit(1)

    c = sqlite3.connect(DB, timeout=20)
    c.execute('PRAGMA journal_mode=WAL')
    row = c.execute('select mid from modules where module_pkg_name=?', (MODULE,)).fetchone()
    if row:
        mid = row[0]
        c.execute('update modules set apk_path=?, enabled=1, auto_include=0 where mid=?', (apk, mid))
    else:
        cur = c.execute('insert into modules(module_pkg_name,apk_path,enabled,auto_include) values(?,?,1,0)',
                        (MODULE, apk))
        mid = cur.lastrowid
    c.execute('delete from scope where mid=?', (mid,))
    c.execute('insert into scope(mid,app_pkg_name,user_id) values(?,?,0)', (mid, ime))
    c.commit()
    print('模块 mid=%s 已启用，作用域= %s' % (mid, ime))
    for r in c.execute('select module_pkg_name,enabled from modules where mid=?', (mid,)):
        print('  modules:', r)
    for r in c.execute('select app_pkg_name from scope where mid=?', (mid,)):
        print('  scope  :', r[0])
    c.close()


if __name__ == '__main__':
    main()
