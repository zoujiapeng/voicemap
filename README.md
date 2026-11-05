# VoiceMap

安卓上一个只有「一个按钮 + 一个输入框」的 App：**按住按钮 = 按住输入法空格键**。中文输入法长按空格就是语音输入，所以按住说话、松手出字；**输入法界面全程不可见**，识别文字由输入法自己写进本 App 的输入框。

不做任何语音识别。识别引擎 100% 是手机输入法自己的。

---

## 原理（3 条）

**1. 隐身 —— LSPosed 模块注入输入法进程，改窗口参数**

hook 框架类，不碰具体输入法：

```
InputMethodService.showWindow / onStartInput / onStartInputView / onWindowShown
Window.setAttributes
WindowManagerImpl.addView
```

判定用 `InputMethodService.getCurrentInputEditorInfo().packageName`：

| 当前输入目标 | 窗口参数 |
|---|---|
| `com.pj.voicemap`（本 App） | `alpha=0`、`dimAmount=0`、去 `FLAG_DIM_BEHIND`、加 `FLAG_NOT_TOUCHABLE` |
| 其它任何 App | 把**自己改过的那一个窗口**还原 `alpha=1.0`、去掉 `FLAG_NOT_TOUCHABLE` |

键盘、长按语音动效、语音面板都在同一个 `ty=INPUT_METHOD` 窗口里，一次 alpha=0 全覆盖。

**2. 触发 —— 往输入法自己的键盘 View 发一对真实触摸**

```java
keyboardView.dispatchTouchEvent(ACTION_DOWN at (x,y))
... 按住期间不动 ...
keyboardView.dispatchTouchEvent(ACTION_UP   at (x,y))
```

输入法以为是手指长按空格，它自己的长按逻辑原样执行（搜狗：布局里 `L_KEY=Key_Voice`）→ 自己录音 → 自己 ASR → `commitText` 到当前 `InputConnection`（即本 App 的 EditText）。

**3. 定位 —— 自校准，不写死输入法**

- 键盘 View：优先搜狗精准路径（`MainImeServiceDel` 里类型为 `SogouKeyboardView` 的字段），通用路径取 IME 窗口 decor 下**面积最大的可见子 View**。
- 空格坐标：先查缓存（输入法自己的 SharedPreferences，键 `pt_<宽>x<高>`），没有就按「底行居中」试候选点。
- 命中判定（任一）：本进程在录音（`AudioManager.getActiveRecordingConfigurations` 有自己 uid）／窗口树（含 `addView` 收集的浮层窗口）里出现 `voice|speech|mic|record|asr|audio` 命名且 `isShown()` 的视图。
- 命中即存盘并回 ack，App 清掉校准期被按出的字符。

## 数据流

```
App 按钮 DOWN/UP
  → 广播 com.pj.voicemap.TRIGGER  cmd=down|up  （明文广播，receiver 由模块动态注册）
  → 模块在输入法进程注入 ACTION_DOWN / ACTION_UP
  → 输入法自己的语音识别
  → InputConnection.commitText → App 的 EditText
```

## 关键常量

搜狗 8.32 OEM，键盘 View 1080x636（横屏/换皮肤会变，所以走自校准）：

```
x = w * 0.5                                  → 540
y = h * (0.754717 + 0.231132/2) = h*0.870283 → 553.5
```

来自 `assets/default_theme/1080/phone/port/py_26.ini` 的 `[Keyboard] H=0.5889`、`[ROW4] V_OFFSET`、`[Key] H`。空格条水平居中（底行键宽 151+128+102+**253**+102+128+151 px + 对称间隙 = 1080）。

## 文件

```
app/                            触发 App（Manifest / layout / MainActivity）
module/                         LSPosed 模块 ← 全部逻辑在 VoiceMapHook.java
  AndroidManifest.xml           xposedmodule / xposedminversion / xposedscope
  assets/xposed_init            com.pj.voicemap.ime.VoiceMapHook
api/                            Xposed api-82 编译桩（仅编译期，不进 APK）
tools/lspd_enable.py            写 LSPosed 数据库启用模块 + 设作用域（--list 列本机输入法）
apk/                            已签名、实机验证过的构建
voicemap.jks                    签名密钥，pass 都是 voicemap
逆向笔记.md                     搜狗内部方法对照（X1/v2、键码表、dump 输出）
截图/                           实机验证截图
```

## 装 / 编译

```bash
sh install.sh [输入法包名]        # 不给则用系统当前默认输入法；装 2 APK + 设作用域 + 重启 IME 进程
sh build.sh                      # Termux: aapt2 + javac + d8 + apksigner；ANDROID_JAR 可用环境变量指定
```

## 验证（logcat tag `LSPosed-Bridge`）

```
VoiceMap: loaded into com.sohu.inputmethod.sogouoem        # 模块注入成功
VoiceMap: stealth on (showWindow) alpha=0.0 flags=0x81800118   # 键盘隐身
VoiceMap: calib probe (540.0,553.5108) hit=true            # 自校准命中
VoiceMap: DOWN at (540.0,553.5) handled=true               # 触摸注入成功
VoiceMap: stealth restored (showWindow) alpha=1.0          # 切到别的 App 已还原
```

`dumpsys window | grep -A3 'InputMethod}'` 应看到 `ty=INPUT_METHOD ... alpha=0.0`，而 `dumpsys input_method` 的 `mInputShown=true`。

调试命令（都是明文广播）：

```bash
am broadcast -a com.pj.voicemap.TRIGGER --es cmd calibrate -p <ime_pkg>
am broadcast -a com.pj.voicemap.TRIGGER --es cmd stealthoff -p <ime_pkg>   # 临时让键盘显形
am broadcast -a com.pj.voicemap.TRIGGER --es cmd dump -p <ime_pkg>         # 导出键盘视图树+按键表
am broadcast -a com.pj.voicemap.TRIGGER --es cmd down --ef x 540 --ef y 553 -p <ime_pkg>
```

## 坑

- **只对中文输入法有效**：长按空格=语音是搜狗/百度/讯飞/QQ 的约定；Gboard 的语音在工具栏麦克风键，长按空格是移光标/切语言 → 自校准会失败。此时把候选点指到它的麦克风键即可。
- 触发 App 必须**前台且输入框有焦点**，否则 `InputConnection` 不是它，识别结果无处可写。
- 模块不引任何识别 SDK、不录音、不联网；App 也没有录音权限。
- 只有 Hook 在输入法进程里才生效：LSPosed 作用域必须是那个输入法包名。
