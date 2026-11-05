# 语音按键 VoiceMap — 给搜狗输入法加一个「长按就说话、看不见键盘」的触发按钮

一台 OnePlus LE2120（Android 13 / SDK 33，Magisk + LSPosed 1.10.1，默认输入法 `com.sohu.inputmethod.sogouoem` 8.32.0322）上已完成实现并实机验证。

---

## 1. 它做了什么

一个只有 **一个按钮 + 一个输入框** 的 App（`com.pj.voicemap`）：

* **短按按钮** = 按一下输入法空格键（走输入法自己的空格逻辑，插空格）。
* **长按按钮** = 长按输入法空格键 → 触发搜狗输入法**自己的**「长按空格语音输入」：录音 → 搜狗 ASR → 结果直接提交到本 App 的输入框。
* **全过程输入法界面完全不可见**：不是遮挡、不是压暗、不是移到屏幕外，而是把输入法进程自己的窗口（`ty=INPUT_METHOD`）**alpha 置 0** 且不接收触摸。屏幕上只看得到这个 App。
* **不重写识别**：没有自建 ASR、没有调用各家语音 SDK。识别引擎、语音面板、断句、候选、插入位置全部是搜狗原本那一套。
* **不影响输入法原有使用**：只有当「当前输入目标」是本 App 时窗口才透明；切到任何别的 App，窗口立刻恢复 alpha=1.0、可触摸，键盘照常弹出（已实机双向验证，见 §5）。

## 2. 原理

两件事，两个组件。

### 2.1 触发 App（`app/`，包名 `com.pj.voicemap`）

* 全屏、`windowSoftInputMode=adjustNothing|stateAlwaysVisible`，启动后主动 `showSoftInput()`，让输入法**真的处于显示状态**并建好与 EditText 的 `InputConnection`。
* 按钮用 `OnTouchListener` 把 **ACTION_DOWN / ACTION_UP** 转成广播 `com.pj.voicemap.TRIGGER`（`cmd=down|up`），发给输入法进程。按下/抬起是真实事件，所以「按住说话、松手出字」的语义和真机键盘完全一致。

### 2.2 LSPosed 模块（`module/`，包名 `com.pj.voicemap.ime`，作用域 = 搜狗输入法）

模块被注入**搜狗输入法进程**，做两件事：

**(a) 隐身（stealth）**

* Hook `InputMethodService.showWindow / onStartInput / onStartInputView / onWindowShown`，以及 `Window.setAttributes`、`WindowManagerImpl.addView`。
* 判定依据是 `InputMethodService.getCurrentInputEditorInfo().packageName`——即"输入法此刻到底在给谁打字"，这是框架给的权威值。
  * 等于 `com.pj.voicemap` → 把输入法窗口的 `alpha=0`、`dimAmount=0`、去掉 `FLAG_DIM_BEHIND`、加 `FLAG_NOT_TOUCHABLE`（透明且不吃触摸，按钮在键盘区域也能按）。
  * 不等于 → 把**我们改过的那一个窗口**恢复成 `alpha=1.0` 并去掉 `FLAG_NOT_TOUCHABLE`（只恢复自己动过的窗口，不碰搜狗自己的透明窗口）。
* 只看得到该改的那一个窗口：实测搜狗的「长按空格语音」面板（`SpaceVoiceImageView` / `SpaceCurveVoiceInputView`）是画在同一 `ty=INPUT_METHOD` 窗口里的，所以一次 alpha=0 就覆盖键盘 + 语音动效 + 语音面板全部。

**(b) 注入真实触摸**

* 通过反射拿到 `MainImeServiceDel` 实例 → 字段里类型为 `com.sohu.inputmethod.sogou.SogouKeyboardView` 的视图 → 键盘视图。
* 空格键中心坐标（键盘视图本地坐标）来自搜狗自己的主题布局 `assets/default_theme/1080/phone/port/py_26.ini`：
  * `[Keyboard] H=0.5889`、`[ROW4] V_OFFSET=0.754717`、键高 `H=0.231132`
  * `y = 高度 × (0.754717 + 0.231132/2) = 高度 × 0.870283`
  * `x = 宽度 / 2`（空格条在 ROW4 里按实测键宽 151+128+102+**253**+102+128+151 px 加对称间隙，正好居中）
* 在该坐标上向键盘视图 `dispatchTouchEvent()` 一发 `ACTION_DOWN`；按钮抬起时补一发 `ACTION_UP`（`eventTime` 用真实时间差）。中间不插入 MOVE，就是真机「按住不动」的序列，搜狗自己的长按判定（`L_KEY=Key_Voice`）照原样执行。

## 3. 目录结构

```
输入法语音输入/
├── README.md                 本文件
├── 逆向笔记.md              搜狗输入法关键发现（L_KEY=Key_Voice、X1/v2、坐标常量）
├── install.sh                一键安装（装 APK + LSPosed 启用 + 重启输入法进程）
├── build.sh                  在 Termux 上重新编译两个 APK（aapt2+javac+d8+apksigner）
├── apk/
│   ├── voicemap.apk          触发 App
│   └── voicemap-ime.apk      LSPosed 模块
├── app/                      触发 App 源码（AndroidManifest/res/src）
├── module/                   LSPosed 模块源码（manifest/res/assets/xposed_init/src）
├── api/                      Xposed API 编译桩（仅编译期，不进 APK）
└── tools/lspd_enable.py      直接写 LSPosed 数据库启用模块 + 作用域
```

## 4. 安装 / 重新编译

```bash
cd /sdcard/Download/输入法语音输入
sh install.sh            # 装两个 APK + 启用模块 + 重启输入法进程
```

> 手机重启后不需要重装。若换了输入法版本导致失效，重新 `sh build.sh && sh install.sh` 即可。
> 前提：Magisk root + LSPosed（本机已具备）。LSPosed 作用域只勾 `com.sohu.inputmethod.sogouoem`，不勾别的 App。

## 5. 实机验证记录（2026-11-06，OnePlus LE2120 / Android 13）

| 验证项 | 方法 | 结果 |
|---|---|---|
| 模块注入输入法进程 | logcat `LSPosed-Bridge` | `VoiceMap: loaded into com.sohu.inputmethod.sogouoem` ✔ |
| 输入法窗口隐身 | `dumpsys window` | `ty=INPUT_METHOD ... alpha=0.0`，`mInputShown=true`（框架认为已显示，但不可见） ✔ |
| 屏幕上确实看不到键盘 | 长按过程中截图 | 只有「语音按键」App，无键盘、无语音面板、无麦克风动效 ✔ |
| 长按确实走搜狗原生语音 | logcat | `SpaceVoiceImageView` 被 inflate（搜狗长按空格语音动效视图） ✔ |
| 识别文字进本 App 输入框 | 用喇叭播 TTS 让麦克风听到 | 输入框出现搜狗识别结果：`好你好呀，你好。能坚持什么输入？`、`干什么？` ✔ |
| 短按 = 空格 | 111 ms 按下/抬起 | `DOWN/UP handled=true`，走搜狗空格逻辑 ✔ |
| 其他 App 不受影响 | 切 Firefox 聚焦输入框 | 日志 `stealth restored (showWindow) alpha=1.0`，键盘正常可见可点 ✔ |

触摸注入日志（一次长按）：

```
VoiceMap: cmd=down strategy=touch
VoiceMap: spaceCenter x=540.0 y=553.5 view=1080x636 spaceKeyFound=1
VoiceMap: DOWN at (540.0,553.5) handled=true kv=com.sohu.inputmethod.sogou.SogouKeyboardView 1080x636
VoiceMap: cmd=up strategy=touch
VoiceMap: UP after 8990ms handled=true
```

## 6. 可调参数

都不需要改代码，用广播手动调，例如：

```bash
# 临时让输入法恢复可见（调试用）
su -c "am broadcast -a com.pj.voicemap.TRIGGER --es cmd stealthoff -p com.sohu.inputmethod.sogouoem"
su -c "am broadcast -a com.pj.voicemap.TRIGGER --es cmd stealthon  -p com.sohu.inputmethod.sogouoem"

# 手动注入一次长按（绕过按钮，用于校准坐标）
su -c "am broadcast -a com.pj.voicemap.TRIGGER --es cmd down --ef x 540 --ef y 553 -p com.sohu.inputmethod.sogouoem"
su -c "am broadcast -a com.pj.voicemap.TRIGGER --es cmd up -p com.sohu.inputmethod.sogouoem"

# 导出键盘视图树 + 全部按键的 rect/键码（写到输入法自己的 cache/voicemap_dump.txt）
su -c "am broadcast -a com.pj.voicemap.TRIGGER --es cmd dump -p com.sohu.inputmethod.sogouoem"
su -c "cat /data/data/com.sohu.inputmethod.sogouoem/cache/voicemap_dump.txt"

# 换策略：不注入触摸，直接调搜狗内部的语音入口（X1=doOnStartVoiceInput / v2=释放）
su -c "am broadcast -a com.pj.voicemap.TRIGGER --es cmd down --es strategy method -p com.sohu.inputmethod.sogouoem"
su -c "am broadcast -a com.pj.voicemap.TRIGGER --es cmd up --es strategy method -p com.sohu.inputmethod.sogouoem"
```

坐标常量在 `module/src/com/pj/voicemap/ime/VoiceMapHook.java` 的 `spaceCenter()`；若要换皮肤/横屏，先用 `cmd dump` 看 `kv size` 再按同一比例算。

## 7. 已知限制

* 模块里**没有**写死输入法包名：任何输入法进程都能被挂上，隐身只在「当前输入目标是本 App」时生效。换输入法只需把 LSPosed 作用域改成那个输入法包名（`python3 tools/lspd_enable.py <包名>`），打开 App 会自动重新校准空格键位置。
* 触发 App 必须在前台且输入框持有焦点（否则 `InputConnection` 不是它，识别结果自然无处可写）。
* 搜狗首次使用语音会弹自己的引导/权限提示——本方案下它同样是不可见的，若首次使用没出字，把 `stealthoff` 打开、正常用一次搜狗语音、再 `stealthon`。
* 系统级「无障碍/辅助功能」未使用，因此不依赖任何无障碍权限弹窗。


## 9. 换手机 / 换输入法怎么办

**结论：不用改代码，重装一次作用域即可，App 第一次打开会自动校准。**

原理上只有两件事跟输入法有关，而两件都做成了自适配：

**(1) 隐身 —— 本来就与输入法无关。**
所有输入法都是在自己的进程里用 `android.inputmethodservice.InputMethodService` 开窗口，模块 hook 的是这个框架类（`showWindow / onStartInput / onStartInputView / onWindowShown`）+ `Window.setAttributes`，并在「当前输入目标包名 == 本 App」时把窗口 `alpha=0`、加 `FLAG_NOT_TOUCHABLE`；换到别的 App 立刻还原。所以 Gboard、百度、讯飞、QQ、SwiftKey……只要是输入法，就自动适用，模块里没有任何一个输入法的包名或类名。

**(2) 触发 —— 只依赖一条几乎所有输入法都成立的约定：空格条在最下一行、水平居中。**
模块先看有没有存过的坐标（按「输入法 + 键盘尺寸」记在输入法自己的 SharedPreferences 里，键名 `pt_<宽>x<高>`），没有就试候选点，并且**能自己判断这一按有没有真的把语音拉起来**：

* 信号 A：本进程是否开始录音 —— `AudioManager.getActiveRecordingConfigurations()` 里出现自己的 uid；
* 信号 B：输入法窗口树（含它自己新加的浮层窗口）里是否出现了「voice / speech / mic / record / asr / audio」命名且**可见**的视图；
* 信号 C：输入法进程是否新加了一个窗口（很多输入法的语音面板是独立窗口）。

命中就存盘并把结果回给 App（`ack: calibrated 540,553`），App 顺手清掉校准过程中被按出来的字符。本机实测：第一次候选点 `(540, 553.5)` 一发命中，日志 `calib probe (540.0,553.5108) hit=true` → `pt_1080x636 = 540.0,553.5108`。

换手机/换皮肤/横屏后键盘尺寸变了 → 键名不同 → 自动重新校准。

**操作步骤（新机器）**

```bash
# 1. 装 Magisk + LSPosed（已有可跳过）
# 2. 把本目录拷到新手机，然后
cd /sdcard/Download/输入法语音输入
su -c "$PREFIX/bin/python3 tools/lspd_enable.py --list"   # 看本机输入法包名
sh install.sh com.google.android.inputmethod.latin          # 用目标输入法包名
# 3. 打开「语音按键」，等它自动校准完（屏幕上看不到任何键盘，正常）
```

**如果某个输入法校准失败**（`ack: calibrate FAILED`）

说明它的空格外形或位置不符合常规。二选一：
* 手动给坐标：`am broadcast -a com.pj.voicemap.TRIGGER --es cmd down --ef x <px> --ef y <px> -p <输入法包名>` 试出来；
* 或者干脆用「直接调输入法内部语音入口」策略（目前只对搜狗实现了 `X1()/v2()`，见 `逆向笔记.md`）——但仍建议优先用触摸注入，因为它对输入法是 100% 透明的。

**注意**：长按空格=语音是中文输入法（搜狗/百度/讯飞/QQ）的约定；Gboard 的语音是工具栏上的麦克风键，长按空格默认是「移动光标/切换语言」。这种情况下校准会失败 —— 不是模块坏了，而是那个输入法没有这个约定。此时把候选点指到它的麦克风键即可（用上面 `--ef x/y` 手动注入确认位置，再把它写进 `candidates()` 的第一项），或者换一个中文输入法用。


## 10. 仓库与构建说明

* 仓库：<https://github.com/zoujiapeng/voicemap>
* `voicemap.jks`：本项目的签名密钥（storepass / keypass 均为 `voicemap`），随仓库提供是为了让后续编译出的 APK 与已安装版本同签名、可直接覆盖升级。
* `apk/` 里是已经签好名、在本机（OnePlus LE2120 / Android 13 / 搜狗 8.32.0322）实机验证过的构建。
* 重新编译：`sh build.sh`（Termux 内，需 `aapt2 / d8 / javac / apksigner / keytool` 与一个 `android.jar`；`ANDROID_JAR` 可用环境变量覆盖）。
