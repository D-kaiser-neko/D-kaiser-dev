#!/system/bin/sh
# 批量停止低风险应用（已去除高风险系统组件）
# 每步间隔 0.2 秒，终端显示进度

echo "===== 开始处理用户应用 ====="

# 'AList'
echo "[用户] 正在停止: AList (com.github.jing332.alistandroid)"
adb shell am force-stop com.github.jing332.alistandroid


# 'AdGuard'
echo "[用户] 正在停止: AdGuard (com.adguard.android)"
adb shell am force-stop com.adguard.android


# 'AlgerMusicPlayer'
echo "[用户] 正在停止: AlgerMusicPlayer (com.algermusic.app)"
adb shell am force-stop com.algermusic.app


# 'Android Code Studio'
echo "[用户] 正在停止: Android Code Studio (com.tom.rv2ide)"
adb shell am force-stop com.tom.rv2ide


# 'Animeko'
echo "[用户] 正在停止: Animeko (me.him188.ani)"
adb shell am force-stop me.him188.ani


# 'Apktool M'
echo "[用户] 正在停止: Apktool M (ru.maximoff.apktool)"
adb shell am force-stop ru.maximoff.apktool


# 'Authenticator'
echo "[用户] 正在停止: Authenticator (com.azure.authenticator)"
adb shell am force-stop com.azure.authenticator


# 'AxManager'
echo "[用户] 正在停止: AxManager (frb.axeron.manager)"
adb shell am force-stop frb.axeron.manager


# 'Bangumi'
echo "[用户] 正在停止: Bangumi (com.czy0729.bangumi)"
adb shell am force-stop com.czy0729.bangumi


# 'ConnectBot'
echo "[用户] 正在停止: ConnectBot (org.connectbot)"
adb shell am force-stop org.connectbot


# 'DeepSeek'
echo "[用户] 正在停止: DeepSeek (com.deepseek.chat)"
adb shell am force-stop com.deepseek.chat


# 'Image Toolbox'
echo "[用户] 正在停止: Image Toolbox (ru.tech.imageresizershrinker)"
adb shell am force-stop ru.tech.imageresizershrinker


# 'Kazumi'
echo "[用户] 正在停止: Kazumi (com.predidit.kazumi)"
adb shell am force-stop com.predidit.kazumi


# 'Kimi'
echo "[用户] 正在停止: Kimi (com.moonshot.kimichat)"
adb shell am force-stop com.moonshot.kimichat


# 'LocalSend'
echo "[用户] 正在停止: LocalSend (org.localsend.localsend_app)"
adb shell am force-stop org.localsend.localsend_app


# 'NP管理器'
echo "[用户] 正在停止: NP管理器 (com.wn.app.np)"
adb shell am force-stop com.wn.app.np


# 'Proton VPN'
echo "[用户] 正在停止: Proton VPN (ch.protonvpn.android)"
adb shell am force-stop ch.protonvpn.android


# 'RAR'
echo "[用户] 正在停止: RAR (com.rarlab.rar)"
adb shell am force-stop com.rarlab.rar


# 'RPlayer'
echo "[用户] 正在停止: RPlayer (com.r.rplayer)"
adb shell am force-stop com.r.rplayer


# 'RealSR BigImage'
echo "[用户] 正在停止: RealSR BigImage (com.tumuyan.ncnn.realsr)"
adb shell am force-stop com.tumuyan.ncnn.realsr


# 'Reqable'
echo "[用户] 正在停止: Reqable (com.reqable.android)"
adb shell am force-stop com.reqable.android


# 'SuperImage'
echo "[用户] 正在停止: SuperImage (com.zhenxiang.superimage)"
adb shell am force-stop com.zhenxiang.superimage


# 'VLC'
echo "[用户] 正在停止: VLC (org.videolan.vlc)"
adb shell am force-stop org.videolan.vlc


# 'VPhoneOS'
echo "[用户] 正在停止: VPhoneOS (com.vphoneos.titan)"
adb shell am force-stop com.vphoneos.titan


# 'Via'
echo "[用户] 正在停止: Via (mark.vib)"
adb shell am force-stop mark.vib


# 'WebServ'
echo "[用户] 正在停止: WebServ (org.join.web.serv)"
adb shell am force-stop org.join.web.serv


# 'Winlator'
echo "[用户] 正在停止: Winlator (com.winlator)"
adb shell am force-stop com.winlator


# 'aShell You'
echo "[用户] 正在停止: aShell You (in.hridayan.ashell)"
adb shell am force-stop in.hridayan.ashell


# 'venera'
echo "[用户] 正在停止: venera (com.github.wgh136.venera)"
adb shell am force-stop com.github.wgh136.venera


# 'vivo Account'
echo "[用户] 正在停止: vivo Account (com.bbk.account)"
adb shell am force-stop com.bbk.account


# '万能电子书阅读器'
echo "[用户] 正在停止: 万能电子书阅读器 (com.kk.xx.book.reader)"
adb shell am force-stop com.kk.xx.book.reader


# '乱七八糟'
echo "[用户] 正在停止: 乱七八糟 (com.all.inclusive)"
adb shell am force-stop com.all.inclusive


# 'Baseus'
echo "[用户] 正在停止: Baseus (com.baseus.intelligent)"
adb shell am force-stop com.baseus.intelligent


# 'bilibili'
echo "[用户] 正在停止: bilibili (tv.danmaku.bili)"
adb shell am force-stop tv.danmaku.bili


# 'AHAspeed'
echo "[用户] 正在停止: AHAspeed (com.ahaspeed5.app)"
adb shell am force-stop com.ahaspeed5.app


# 'Wallpaper Engine'
echo "[用户] 正在停止: Wallpaper Engine (io.wallpaperengine.weclient)"
adb shell am force-stop io.wallpaperengine.weclient


# '夸克'
echo "[用户] 正在停止: 夸克 (com.quark.browser)"
adb shell am force-stop com.quark.browser


# 'AI Adviser'
echo "[用户] 正在停止: AI Adviser (com.vivo.assistant)"
adb shell am force-stop com.vivo.assistant


# 'Tiny Container'
echo "[用户] 正在停止: Tiny Container (com.fct.tc4)"
adb shell am force-stop com.fct.tc4


# '小熊加速器'
echo "[用户] 正在停止: 小熊加速器 (com.justsoso.fastes)"
adb shell am force-stop com.justsoso.fastes


# 'Dev Tools'
echo "[用户] 正在停止: Dev Tools (cn.trinea.android.developertools)"
adb shell am force-stop cn.trinea.android.developertools


# '心听'
echo "[用户] 正在停止: 心听 (tingxin.pwl.android.ny)"
adb shell am force-stop tingxin.pwl.android.ny


# 'Drag & go'
echo "[用户] 正在停止: Drag & go (com.vivo.globaldragdrop)"
adb shell am force-stop com.vivo.globaldragdrop


# '暮光工具箱'
echo "[用户] 正在停止: 暮光工具箱 (com.twilight.toolsapp)"
adb shell am force-stop com.twilight.toolsapp


# 'Immersive Translate'
echo "[用户] 正在停止: Immersive Translate (com.immersivetranslate.browser)"
adb shell am force-stop com.immersivetranslate.browser


# '百词斩'
echo "[用户] 正在停止: 百词斩 (com.jiongji.andriod.card)"
adb shell am force-stop com.jiongji.andriod.card


# '蓝奏云优享版'
echo "[用户] 正在停止: 蓝奏云优享版 (com.ilanzou.app.disk)"
adb shell am force-stop com.ilanzou.app.disk


# 'Material Files'
echo "[用户] 正在停止: Material Files (me.zhanghai.android.files)"
adb shell am force-stop me.zhanghai.android.files


# '轻小说文库'
echo "[用户] 正在停止: 轻小说文库 (org.mewx.wenku8)"
adb shell am force-stop org.mewx.wenku8


# 'Universal Installer'
echo "[用户] 正在停止: Universal Installer (app.pwhs.universalinstaller)"
adb shell am force-stop app.pwhs.universalinstaller


# 'Lockscreen Poster'
echo "[用户] 正在停止: Lockscreen Poster (com.vivo.magazine)"
adb shell am force-stop com.vivo.magazine


echo "===== 用户应用处理完毕，开始处理低风险系统应用 ====="

# 'AIService'
echo "[系统] 正在停止: AIService (com.vivo.aiservice)"
adb shell am force-stop com.vivo.aiservice


# 'Android Easter Egg'
echo "[系统] 正在停止: Android Easter Egg (com.android.egg)"
adb shell am force-stop com.android.egg


# 'Android Accessibility Suite'
echo "[系统] 正在停止: Android Accessibility Suite (com.google.android.marvin.talkback)"
adb shell am force-stop com.google.android.marvin.talkback


# 'Google One Time Init'
echo "[系统] 正在停止: Google One Time Init (com.google.android.onetimeinitializer)"
adb shell am force-stop com.google.android.onetimeinitializer


# 'Google Play Services Updater'
echo "[系统] 正在停止: Google Play Services Updater (com.android.vending)"
adb shell am force-stop com.android.vending


# 'Google Calendar Sync'
echo "[系统] 正在停止: Google Calendar Sync (com.google.android.syncadapters.calendar)"
adb shell am force-stop com.google.android.syncadapters.calendar


# 'Clock and weather'
echo "[系统] 正在停止: Clock and weather (com.vivo.doubletimezoneclock)"
adb shell am force-stop com.vivo.doubletimezoneclock


# 'vivo experience assessment'
echo "[系统] 正在停止: vivo experience assessment (com.vivo.nps)"
adb shell am force-stop com.vivo.nps


# 'vivo TWS'
echo "[系统] 正在停止: vivo TWS (com.android.vivo.tws.vivotws)"
adb shell am force-stop com.android.vivo.tws.vivotws


# 'VAS Core'
echo "[系统] 正在停止: VAS Core (com.vivo.connbase.deviceaccessory)"
adb shell am force-stop com.vivo.connbase.deviceaccessory


# 'vivoshare'
echo "[系统] 正在停止: vivoshare (com.vivo.share)"
adb shell am force-stop com.vivo.share


# 'vivo Office Kit'
echo "[系统] 正在停止: vivo Office Kit (com.vivo.pcsuite)"
adb shell am force-stop com.vivo.pcsuite


# 'vivo Docs'
echo "[系统] 正在停止: vivo Docs (com.vivo.smartoffice)"
adb shell am force-stop com.vivo.smartoffice


# 'vivo services security plugin'
echo "[系统] 正在停止: vivo services security plugin (com.vivo.sdkplugin)"
adb shell am force-stop com.vivo.sdkplugin


# 'vivo Account'
echo "[系统] 正在停止: vivo Account (com.bbk.account)"
adb shell am force-stop com.bbk.account


# 'Download management'
echo "[系统] 正在停止: Download management (com.android.providers.downloads.ui)"
adb shell am force-stop com.android.providers.downloads.ui


# 'vivoCloud'
echo "[系统] 正在停止: vivoCloud (com.bbk.cloud)"
adb shell am force-stop com.bbk.cloud


# 'EasyShare'
echo "[系统] 正在停止: EasyShare (com.vivo.easyshare)"
adb shell am force-stop com.vivo.easyshare


# 'Messages'
echo "[系统] 正在停止: Messages (com.android.mms)"
adb shell am force-stop com.android.mms


# 'Digital Wellbeing'
echo "[系统] 正在停止: Digital Wellbeing (com.vivo.familycare.local)"
adb shell am force-stop com.vivo.familycare.local


# 'Health Care'
echo "[系统] 正在停止: Health Care (com.vivo.widget.healthcare)"
adb shell am force-stop com.vivo.widget.healthcare


# 'Health Connect'
echo "[系统] 正在停止: Health Connect (com.android.healthconnect.controller)"
adb shell am force-stop com.android.healthconnect.controller


# 'Health Service'
echo "[系统] 正在停止: Health Service (com.vivo.healthservice)"
adb shell am force-stop com.vivo.healthservice


# 'Health kit'
echo "[系统] 正在停止: Health kit (com.vivo.healthwidget)"
adb shell am force-stop com.vivo.healthwidget


# 'Kids Zone'
echo "[系统] 正在停止: Kids Zone (com.vivo.childrenmode)"
adb shell am force-stop com.vivo.childrenmode


# 'Global search'
echo "[系统] 正在停止: Global search (com.vivo.globalsearch)"
adb shell am force-stop com.vivo.globalsearch


# 'Dynamic lockscreen service'
echo "[系统] 正在停止: Dynamic lockscreen service (com.vlife.vivo.wallpaper)"
adb shell am force-stop com.vlife.vivo.wallpaper


# 'Card center'
echo "[系统] 正在停止: Card center (com.vivo.cardstore)"
adb shell am force-stop com.vivo.cardstore


# 'Origin Player'
echo "[系统] 正在停止: Origin Player (com.vivo.musicwidgetmix)"
adb shell am force-stop com.vivo.musicwidgetmix


# 'Mood Cube'
echo "[系统] 正在停止: Mood Cube (com.vivo.moodcube)"
adb shell am force-stop com.vivo.moodcube


# 'Sound localization training center'
echo "[系统] 正在停止: Sound localization training center (com.vivo.gametrain)"
adb shell am force-stop com.vivo.gametrain


# 'Image viewing'
echo "[系统] 正在停止: Image viewing (com.vivo.base.gallery)"
adb shell am force-stop com.vivo.base.gallery


# 'Sound recognition'
echo "[系统] 正在停止: Sound recognition (com.vivo.voicerecognition)"
adb shell am force-stop com.vivo.voicerecognition


# '多场景安全支付服务'
echo "[系统] 正在停止: 多场景安全支付服务 (com.vivo.pay)"
adb shell am force-stop com.vivo.pay


# 'Weather'
echo "[系统] 正在停止: Weather (com.vivo.weather)"
adb shell am force-stop com.vivo.weather


# 'Weather storage'
echo "[系统] 正在停止: Weather storage (com.vivo.weather.provider)"
adb shell am force-stop com.vivo.weather.provider


# 'Weather kit'
echo "[系统] 正在停止: Weather kit (com.vivo.widgetweather)"
adb shell am force-stop com.vivo.widgetweather


# 'Weather (lite)'
echo "[系统] 正在停止: Weather (lite) (com.vivo.dream.weather)"
adb shell am force-stop com.vivo.dream.weather


# 'Task timer'
echo "[系统] 正在停止: Task timer (com.android.BBKCrontab)"
adb shell am force-stop com.android.BBKCrontab


# 'AI Note-taking'
echo "[系统] 正在停止: AI Note-taking (com.vivo.screenagent)"
adb shell am force-stop com.vivo.screenagent


# 'AI Reader'
echo "[系统] 正在停止: AI Reader (com.vivo.screenreader)"
adb shell am force-stop com.vivo.screenreader


# 'AI Adviser'
echo "[系统] 正在停止: AI Adviser (com.vivo.assistant)"
adb shell am force-stop com.vivo.assistant


# 'AI Memory'
echo "[系统] 正在停止: AI Memory (com.vivo.favorite)"
adb shell am force-stop com.vivo.favorite


# 'Screen time widget'
echo "[系统] 正在停止: Screen time widget (com.vivo.widget.timemanager)"
adb shell am force-stop com.vivo.widget.timemanager


# 'Ad Privacy'
echo "[系统] 正在停止: Ad Privacy (com.android.adservices.api)"
adb shell am force-stop com.android.adservices.api


# 'V-Appstore'
echo "[系统] 正在停止: V-Appstore (com.bbk.appstore)"
adb shell am force-stop com.bbk.appstore


# 'App suggestions kit'
echo "[系统] 正在停止: App suggestions kit (com.vivo.appsuggestion)"
adb shell am force-stop com.vivo.appsuggestion


# 'Quick App Frame Service'
echo "[系统] 正在停止: Quick App Frame Service (com.vivo.hybrid)"
adb shell am force-stop com.vivo.hybrid


# '快捷指令组件'
echo "[系统] 正在停止: 快捷指令组件 (com.vivo.ai.copilot.shortcut.component)"
adb shell am force-stop com.vivo.ai.copilot.shortcut.component


# 'Feedback'
echo "[系统] 正在停止: Feedback (com.bbk.iqoo.feedback)"
adb shell am force-stop com.bbk.iqoo.feedback


# 'Scan (base)'
echo "[系统] 正在停止: Scan (com.vivo.base.vtouch)"
adb shell am force-stop com.vivo.base.vtouch


# 'Scan'
echo "[系统] 正在停止: Scan (com.vivo.vtouch)"
adb shell am force-stop com.vivo.vtouch


# 'Screen Mirroring'
echo "[系统] 正在停止: Screen Mirroring (com.vivo.upnpserver)"
adb shell am force-stop com.vivo.upnpserver


# 'Compass'
echo "[系统] 正在停止: Compass (com.vivo.compass)"
adb shell am force-stop com.vivo.compass


# 'Push Engine'
echo "[系统] 正在停止: Push Engine (com.vivo.pushservice)"
adb shell am force-stop com.vivo.pushservice


# 'File Manager'
echo "[系统] 正在停止: File Manager (com.android.filemanager)"
adb shell am force-stop com.android.filemanager


# 'Calendar'
echo "[系统] 正在停止: Calendar (com.bbk.calendar)"
adb shell am force-stop com.bbk.calendar


# 'Calendar widget'
echo "[系统] 正在停止: Calendar widget (com.vivo.widget.calendar)"
adb shell am force-stop com.vivo.widget.calendar


# 'Log Collection'
echo "[系统] 正在停止: Log Collection (com.android.bbklog)"
adb shell am force-stop com.android.bbklog


# 'Clock (lite)'
echo "[系统] 正在停止: Clock (lite) (com.vivo.dream.clock)"
adb shell am force-stop com.vivo.dream.clock


# 'Smart Engine'
echo "[系统] 正在停止: Smart Engine (com.vivo.abe)"
adb shell am force-stop com.vivo.abe


# 'Smart service'
echo "[系统] 正在停止: Smart service (com.vivo.aiengine)"
adb shell am force-stop com.vivo.aiengine


# 'Jovi InLife service'
echo "[系统] 正在停止: Jovi InLife service (com.vivo.smartLife)"
adb shell am force-stop com.vivo.smartLife


# 'Smart Motion'
echo "[系统] 正在停止: Smart Motion (com.vivo.motionrecognition)"
adb shell am force-stop com.vivo.motionrecognition


# '智能体服务'
echo "[系统] 正在停止: 智能体服务 (com.vivo.ai.gptagent)"
adb shell am force-stop com.vivo.ai.gptagent


# 'Jovi语音'
echo "[系统] 正在停止: Jovi语音 (com.vivo.agent)"
adb shell am force-stop com.vivo.agent


# 'Jovi InCar'
echo "[系统] 正在停止: Jovi InCar (com.vivo.car.networking)"
adb shell am force-stop com.vivo.car.networking


# 'Smart Remote'
echo "[系统] 正在停止: Smart Remote (com.vivo.smartremote)"
adb shell am force-stop com.vivo.smartremote


# 'Find'
echo "[系统] 正在停止: Find (com.vivo.findphone)"
adb shell am force-stop com.vivo.findphone


# 'Home screen search'
echo "[系统] 正在停止: Home screen search (com.vivo.puresearch)"
adb shell am force-stop com.vivo.puresearch


# 'Data Store'
echo "[系统] 正在停止: Data Store (com.mobile.iroaming)"
adb shell am force-stop com.mobile.iroaming


# 'Browser'
echo "[系统] 正在停止: Browser (com.vivo.browser)"
adb shell am force-stop com.vivo.browser


# 'Cleanup kit'
echo "[系统] 正在停止: Cleanup kit (com.vivo.widget.cleanspeed)"
adb shell am force-stop com.vivo.widget.cleanspeed


# '用户体验改进计划服务'
echo "[系统] 正在停止: 用户体验改进计划服务 (com.bbk.iqoo.logsystem)"
adb shell am force-stop com.bbk.iqoo.logsystem


# 'Albums'
echo "[系统] 正在停止: Albums (com.vivo.gallery)"
adb shell am force-stop com.vivo.gallery


# 'Album highlights'
echo "[系统] 正在停止: Album highlights (com.vivo.widget.gallery)"
adb shell am force-stop com.vivo.widget.gallery


# 'Camera'
echo "[系统] 正在停止: Camera (com.android.camera)"
adb shell am force-stop com.android.camera


# 'Mobile KTV'
echo "[系统] 正在停止: Mobile KTV (com.vivo.vivokaraoke)"
adb shell am force-stop com.vivo.vivokaraoke


# 'Recommends'
echo "[系统] 正在停止: Recommends (com.vivo.are)"
adb shell am force-stop com.vivo.are


# 'Translator'
echo "[系统] 正在停止: Translator (com.vivo.translator)"
adb shell am force-stop com.vivo.translator


# 'Energy Cube'
echo "[系统] 正在停止: Energy Cube (com.vivo.livewallpaper.behavioriqoo)"
adb shell am force-stop com.vivo.livewallpaper.behavioriqoo


# '蓝心小V (base)'
echo "[系统] 正在停止: 蓝心小V (com.vivo.ai.base.copilot)"
adb shell am force-stop com.vivo.ai.base.copilot


# '蓝心小V'
echo "[系统] 正在停止: 蓝心小V (com.vivo.ai.copilot)"
adb shell am force-stop com.vivo.ai.copilot


# 'Vision accessibility'
echo "[系统] 正在停止: Vision accessibility (com.vivo.visionaid.builtin)"
adb shell am force-stop com.vivo.visionaid.builtin


# 'Video'
echo "[系统] 正在停止: Video (com.android.VideoPlayer)"
adb shell am force-stop com.android.VideoPlayer


# 'Timer kit'
echo "[系统] 正在停止: Timer kit (com.vivo.countdownwidget)"
adb shell am force-stop com.vivo.countdownwidget


# 'Calculator'
echo "[系统] 正在停止: Calculator (com.android.bbkcalculator)"
adb shell am force-stop com.android.bbkcalculator


# 'Voice wakeup'
echo "[系统] 正在停止: Voice wakeup (com.vivo.voicewakeup)"
adb shell am force-stop com.vivo.voicewakeup


# 'Stickers'
echo "[系统] 正在停止: Stickers (com.vivo.desktopstickers)"
adb shell am force-stop com.vivo.desktopstickers


# 'Super screenshot'
echo "[系统] 正在停止: Super screenshot (com.vivo.smartshot)"
adb shell am force-stop com.vivo.smartshot


# 'InCar Launcher'
echo "[系统] 正在停止: InCar Launcher (com.vivo.carlauncher)"
adb shell am force-stop com.vivo.carlauncher


# 'Lockscreen Poster'
echo "[系统] 正在停止: Lockscreen Poster (com.vivo.magazine)"
adb shell am force-stop com.vivo.magazine


# 'Audio effect'
echo "[系统] 正在停止: Audio effect (com.vivo.audiofx)"
adb shell am force-stop com.vivo.audiofx


echo "===== 全部应用处理完毕 ====="