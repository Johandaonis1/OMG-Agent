"""App package name mappings.

This module keeps protocol-specific mappings aligned with upstream projects:
- Open-AutoGLM: `phone_agent/config/apps.py::APP_PACKAGES`
- GELab-Zero: `copilot_front_end/package_map.py::package_name_map`

The universal mapping remains for backward compatibility, but when running
in `autoglm` or `gelab` protocol we route to the official-aligned resolver.
"""

# Common app name to package name mapping
APP_PACKAGE_MAP: dict[str, str] = {
    # Social
    "wechat": "com.tencent.mm",
    "weixin": "com.tencent.mm",
    "qq": "com.tencent.mobileqq",
    "weibo": "com.sina.weibo",
    "dingtalk": "com.alibaba.android.rimet",
    "feishu": "com.ss.android.lark",
    "telegram": "org.telegram.messenger",
    "whatsapp": "com.whatsapp",

    # Shopping
    "taobao": "com.taobao.taobao",
    "jd": "com.jingdong.app.mall",
    "jingdong": "com.jingdong.app.mall",
    "pinduoduo": "com.xunmeng.pinduoduo",
    "xianyu": "com.taobao.idlefish",

    # Food & Delivery
    "meituan": "com.sankuai.meituan",
    "eleme": "me.ele",
    "dianping": "com.dianping.v1",

    # Travel
    "gaode": "com.autonavi.minimap",
    "amap": "com.autonavi.minimap",
    "baidu_map": "com.baidu.BaiduMap",
    "didi": "com.sdu.didi.psnger",
    "ctrip": "ctrip.android.view",
    "12306": "com.MobileTicket",

    # Video
    "douyin": "com.ss.android.ugc.aweme",
    "tiktok": "com.zhiliaoapp.musically",
    "kuaishou": "com.smile.gifmaker",
    "bilibili": "tv.danmaku.bili",
    "tencent_video": "com.tencent.qqlive",
    "youku": "com.youku.phone",
    "iqiyi": "com.qiyi.video",

    # Music
    "netease_music": "com.netease.cloudmusic",
    "qq_music": "com.tencent.qqmusic",
    "kugou": "com.kugou.android",
    "ximalaya": "com.ximalaya.ting.android",

    # Social/Community
    "xiaohongshu": "com.xingin.xhs",
    "zhihu": "com.zhihu.android",
    "douban": "com.douban.frodo",

    # Tools
    "chrome": "com.android.chrome",
    "settings": "com.android.settings",
    "camera": "com.android.camera",
    "gallery": "com.android.gallery3d",
    "calculator": "com.android.calculator2",
    "clock": "com.android.deskclock",
    "calendar": "com.android.calendar",
    "contacts": "com.android.contacts",
    "messages": "com.android.mms",
    "phone": "com.android.dialer",
    "files": "com.android.documentsui",

    # Others
    "alipay": "com.eg.android.AlipayGphone",
    "unionpay": "com.unionpay",
    "cainiao": "com.cainiao.wireless",
    "keep": "com.gotokeep.keep",
}

# Alternative names mapping
APP_ALIASES: dict[str, str] = {
    "wechat": "weixin",
    "jingdong": "jd",
    "amap": "gaode",
    "tiktok": "douyin",
    "netease": "netease_music",
    "wymusic": "netease_music",
    "qqmusic": "qq_music",
    "red": "xiaohongshu",
    "xhs": "xiaohongshu",
}


# =============================================================================
# Open-AutoGLM official mapping (keep insertion order)
# =============================================================================

AUTOGLM_APP_PACKAGES: dict[str, str] = {
    "微信": "com.tencent.mm",
    "QQ": "com.tencent.mobileqq",
    "微博": "com.sina.weibo",
    "淘宝": "com.taobao.taobao",
    "京东": "com.jingdong.app.mall",
    "拼多多": "com.xunmeng.pinduoduo",
    "淘宝闪购": "com.taobao.taobao",
    "京东秒送": "com.jingdong.app.mall",
    "小红书": "com.xingin.xhs",
    "豆瓣": "com.douban.frodo",
    "知乎": "com.zhihu.android",
    "高德地图": "com.autonavi.minimap",
    "百度地图": "com.baidu.BaiduMap",
    "美团": "com.sankuai.meituan",
    "大众点评": "com.dianping.v1",
    "饿了么": "me.ele",
    "肯德基": "com.yek.android.kfc.activitys",
    "携程": "ctrip.android.view",
    "铁路12306": "com.MobileTicket",
    "12306": "com.MobileTicket",
    "去哪儿": "com.Qunar",
    "去哪儿旅行": "com.Qunar",
    "滴滴出行": "com.sdu.didi.psnger",
    "bilibili": "tv.danmaku.bili",
    "抖音": "com.ss.android.ugc.aweme",
    "快手": "com.smile.gifmaker",
    "腾讯视频": "com.tencent.qqlive",
    "爱奇艺": "com.qiyi.video",
    "优酷视频": "com.youku.phone",
    "芒果TV": "com.hunantv.imgo.activity",
    "红果短剧": "com.phoenix.read",
    "网易云音乐": "com.netease.cloudmusic",
    "QQ音乐": "com.tencent.qqmusic",
    "汽水音乐": "com.luna.music",
    "喜马拉雅": "com.ximalaya.ting.android",
    "番茄小说": "com.dragon.read",
    "番茄免费小说": "com.dragon.read",
    "七猫免费小说": "com.kmxs.reader",
    "飞书": "com.ss.android.lark",
    "QQ邮箱": "com.tencent.androidqqmail",
    "豆包": "com.larus.nova",
    "keep": "com.gotokeep.keep",
    "美柚": "com.lingan.seeyou",
    "腾讯新闻": "com.tencent.news",
    "今日头条": "com.ss.android.article.news",
    "贝壳找房": "com.lianjia.beike",
    "安居客": "com.anjuke.android.app",
    "同花顺": "com.hexin.plat.android",
    "星穹铁道": "com.miHoYo.hkrpg",
    "崩坏：星穹铁道": "com.miHoYo.hkrpg",
    "恋与深空": "com.papegames.lysk.cn",
    "AndroidSystemSettings": "com.android.settings",
    "Android System Settings": "com.android.settings",
    "Android  System Settings": "com.android.settings",
    "Android-System-Settings": "com.android.settings",
    "Settings": "com.android.settings",
    "AudioRecorder": "com.android.soundrecorder",
    "audiorecorder": "com.android.soundrecorder",
    "Bluecoins": "com.rammigsoftware.bluecoins",
    "bluecoins": "com.rammigsoftware.bluecoins",
    "Broccoli": "com.flauschcode.broccoli",
    "broccoli": "com.flauschcode.broccoli",
    "Booking.com": "com.booking",
    "Booking": "com.booking",
    "booking.com": "com.booking",
    "booking": "com.booking",
    "BOOKING.COM": "com.booking",
    "Chrome": "com.android.chrome",
    "chrome": "com.android.chrome",
    "Google Chrome": "com.android.chrome",
    "Clock": "com.android.deskclock",
    "clock": "com.android.deskclock",
    "Contacts": "com.android.contacts",
    "contacts": "com.android.contacts",
    "Duolingo": "com.duolingo",
    "duolingo": "com.duolingo",
    "Expedia": "com.expedia.bookings",
    "expedia": "com.expedia.bookings",
    "Files": "com.android.fileexplorer",
    "files": "com.android.fileexplorer",
    "File Manager": "com.android.fileexplorer",
    "file manager": "com.android.fileexplorer",
    "gmail": "com.google.android.gm",
    "Gmail": "com.google.android.gm",
    "GoogleMail": "com.google.android.gm",
    "Google Mail": "com.google.android.gm",
    "GoogleFiles": "com.google.android.apps.nbu.files",
    "googlefiles": "com.google.android.apps.nbu.files",
    "FilesbyGoogle": "com.google.android.apps.nbu.files",
    "GoogleCalendar": "com.google.android.calendar",
    "Google-Calendar": "com.google.android.calendar",
    "Google Calendar": "com.google.android.calendar",
    "google-calendar": "com.google.android.calendar",
    "google calendar": "com.google.android.calendar",
    "GoogleChat": "com.google.android.apps.dynamite",
    "Google Chat": "com.google.android.apps.dynamite",
    "Google-Chat": "com.google.android.apps.dynamite",
    "GoogleClock": "com.google.android.deskclock",
    "Google Clock": "com.google.android.deskclock",
    "Google-Clock": "com.google.android.deskclock",
    "GoogleContacts": "com.google.android.contacts",
    "Google-Contacts": "com.google.android.contacts",
    "Google Contacts": "com.google.android.contacts",
    "google-contacts": "com.google.android.contacts",
    "google contacts": "com.google.android.contacts",
    "GoogleDocs": "com.google.android.apps.docs.editors.docs",
    "Google Docs": "com.google.android.apps.docs.editors.docs",
    "googledocs": "com.google.android.apps.docs.editors.docs",
    "google docs": "com.google.android.apps.docs.editors.docs",
    "Google Drive": "com.google.android.apps.docs",
    "Google-Drive": "com.google.android.apps.docs",
    "google drive": "com.google.android.apps.docs",
    "google-drive": "com.google.android.apps.docs",
    "GoogleDrive": "com.google.android.apps.docs",
    "Googledrive": "com.google.android.apps.docs",
    "googledrive": "com.google.android.apps.docs",
    "GoogleFit": "com.google.android.apps.fitness",
    "googlefit": "com.google.android.apps.fitness",
    "GoogleKeep": "com.google.android.keep",
    "googlekeep": "com.google.android.keep",
    "GoogleMaps": "com.google.android.apps.maps",
    "Google Maps": "com.google.android.apps.maps",
    "googlemaps": "com.google.android.apps.maps",
    "google maps": "com.google.android.apps.maps",
    "Google Play Books": "com.google.android.apps.books",
    "Google-Play-Books": "com.google.android.apps.books",
    "google play books": "com.google.android.apps.books",
    "google-play-books": "com.google.android.apps.books",
    "GooglePlayBooks": "com.google.android.apps.books",
    "googleplaybooks": "com.google.android.apps.books",
    "GooglePlayStore": "com.android.vending",
    "Google Play Store": "com.android.vending",
    "Google-Play-Store": "com.android.vending",
    "GoogleSlides": "com.google.android.apps.docs.editors.slides",
    "Google Slides": "com.google.android.apps.docs.editors.slides",
    "Google-Slides": "com.google.android.apps.docs.editors.slides",
    "GoogleTasks": "com.google.android.apps.tasks",
    "Google Tasks": "com.google.android.apps.tasks",
    "Google-Tasks": "com.google.android.apps.tasks",
    "Joplin": "net.cozic.joplin",
    "joplin": "net.cozic.joplin",
    "McDonald": "com.mcdonalds.app",
    "mcdonald": "com.mcdonalds.app",
    "Osmand": "net.osmand",
    "osmand": "net.osmand",
    "PiMusicPlayer": "com.Project100Pi.themusicplayer",
    "pimusicplayer": "com.Project100Pi.themusicplayer",
    "Quora": "com.quora.android",
    "quora": "com.quora.android",
    "Reddit": "com.reddit.frontpage",
    "reddit": "com.reddit.frontpage",
    "RetroMusic": "code.name.monkey.retromusic",
    "retromusic": "code.name.monkey.retromusic",
    "SimpleCalendarPro": "com.scientificcalculatorplus.simplecalculator.basiccalculator.mathcalc",
    "SimpleSMSMessenger": "com.simplemobiletools.smsmessenger",
    "Telegram": "org.telegram.messenger",
    "temu": "com.einnovation.temu",
    "Temu": "com.einnovation.temu",
    "Tiktok": "com.zhiliaoapp.musically",
    "tiktok": "com.zhiliaoapp.musically",
    "Twitter": "com.twitter.android",
    "twitter": "com.twitter.android",
    "X": "com.twitter.android",
    "VLC": "org.videolan.vlc",
    "WeChat": "com.tencent.mm",
    "wechat": "com.tencent.mm",
    "Whatsapp": "com.whatsapp",
    "WhatsApp": "com.whatsapp",
}


def autoglm_app_name_from_package(package_name: str) -> str:
    """
    Map Android package name to Open-AutoGLM's display name.

    Mirrors `Open-AutoGLM/phone_agent/adb/device.py::get_current_app` behavior:
    returns the first matching app name in insertion order; otherwise "System Home".
    """
    if not package_name:
        return "System Home"

    for name, pkg in AUTOGLM_APP_PACKAGES.items():
        if pkg and pkg in package_name:
            return name
    return "System Home"


# =============================================================================
# GELab-Zero official mapping (keep insertion order)
# =============================================================================

GELAB_PACKAGE_NAME_MAP: dict[str, str] = {
    "天气": "com.coloros.weather2",
    "家人守护": "com.coloros.familyguard",
    "美柚": "com.lingan.seeyou",
    "百度极速版": "com.baidu.searchbox.lite",
    "58同城": "com.wuba",
    "知乎": "com.zhihu.android",
    "滴滴出行": "com.sdu.didi.psnger",
    "计算器": "com.coloros.calculator",
    "掌上生活": "com.cmbchina.ccd.pluto.cmbActivity",
    "飞猪旅行": "com.taobao.trip",
    "网易有道词典": "com.youdao.dict",
    "百度贴吧": "com.baidu.tieba",
    "腾讯新闻": "com.tencent.news",
    "饿了么": "me.ele",
    "百度输入法": "com.baidu.input",
    "优酷视频": "com.youku.phone",
    "抖音": "com.ss.android.ugc.aweme",
    "今日头条": "com.ss.android.article.news",
    "酷我音乐": "cn.kuwo.player",
    "oppo社区": "com.oppo.community",
    "夸克": "com.quark.browser",
    "邮件": "com.android.email",
    "美团": "com.sankuai.meituan",
    "剪映": "com.lemon.lv",
    "酷狗概念版": "com.kugou.android.lite",
    "酷狗音乐": "com.kugou.android",
    "网易邮箱大师": "com.netease.mail",
    "番茄免费小说": "com.dragon.read",
    "yy": "com.duowan.mobile",
    "qq": "com.tencent.mobileqq",
    "小宇宙": "app.podcast.cosmos",
    "指南针": "com.coloros.compass2",
    "oppo视频": "com.heytap.yoli",
    "天猫": "com.tmall.wireless",
    "抖音商城": "com.ss.android.ugc.livelite",
    "点淘": "com.taobao.live",
    "录音": "com.coloros.soundrecorder",
    "哔哩哔哩": "tv.danmaku.bili",
    "B站": "tv.danmaku.bili",
    "soul": "cn.soulapp.android",
    "高德地图": "com.autonavi.minimap",
    "懂车帝": "com.ss.android.auto",
    "小红书": "com.xingin.xhs",
    "咪咕视频": "com.cmcc.cmvideo",
    "拼多多": "com.xunmeng.pinduoduo",
    "微信读书": "com.tencent.weread",
    "蘑菇街": "com.mogujie",
    "大众点评": "com.dianping.v1",
    "云闪付": "com.unionpay",
    "好看视频": "com.baidu.haokan",
    "AIAgentDemo": "com.stepfun.aiagent.demo",
    "qq浏览器": "com.tencent.mtt",
    "文件管理": "com.coloros.filemanager",
    "豆瓣": "com.douban.frodo",
    "日历": "com.coloros.calendar",
    "游戏助手": "com.oplus.games",
    "网易云音乐": "com.netease.cloudmusic",
    "中国联通": "com.sinovatech.unicom.ui",
    "喜马拉雅": "com.ximalaya.ting.android",
    "主题商店": "com.heytap.themestore",
    "飞书": "com.ss.android.lark",
    "红袖读书": "com.hongxiu.app",
    "全民K歌": "com.tencent.karaoke",
    "抖音火山版": "com.ss.android.ugc.live",
    "美图秀秀": "com.mt.mtxx.mtxx",
    "拾程旅行": "com.hnjw.shichengtravel",
    "中国电信": "com.ct.client",
    "时钟": "com.coloros.alarmclock",
    "快对": "com.kuaiduizuoye.scan",
    "钱包": "com.finshell.wallet",
    "快手极速版": "com.kuaishou.nebula",
    "文件随心开": "cn.wps.moffice.lite",
    "微博": "com.sina.weibo",
    "墨迹天气": "com.moji.mjweather",
    "kimi 智能助手": "com.moonshot.kimichat",
    "起点读书": "com.qidian.QDReader",
    "逍遥游": "com.redteamobile.roaming",
    "豆包": "com.larus.nova",
    "平安好车主": "com.pingan.carowner",
    "去哪儿旅行": "com.Qunar",
    "银联可信服务安全组件": "com.unionpay.tsmservice",
    "腾讯微视": "com.tencent.weishi",
    "网上国网": "com.sgcc.wsgw.cn",
    "作业帮": "com.baidu.homework",
    "阅读": "com.heytap.reader",
    "keep": "com.gotokeep.keep",
    "蜻蜓FM": "fm.qingting.qtradio",
    "禅定空间": "com.oneplus.brickmode",
    "腾讯地图": "com.tencent.map",
    "虎牙直播": "com.duowan.kiwi",
    "番茄畅听音乐版": "com.xs.fm.lite",
    "今日头条极速版": "com.ss.android.article.lite",
    "转转": "com.wuba.zhuanzhuan",
    "芒果TV": "com.hunantv.imgo.activity",
    "便签": "com.coloros.note",
    "UC浏览器": "com.UCMobile",
    "百度文库": "com.baidu.wenku",
    "小猿搜题": "com.fenbi.android.solar",
    "腾讯文档": "com.tencent.docs",
    "携程旅行": "ctrip.android.view",
    "wpsoffice": "cn.wps.moffice_eng",
    "哈啰": "com.jingyao.easybike",
    "中国移动": "com.greenpoint.android.mc10086.activity",
    "唯品会": "com.achievo.vipshop",
    "手机 搬家": "com.coloros.backuprestore",
    "安逸花": "com.msxf.ayh",
    "汽水音乐": "com.luna.music",
    "音乐": "com.heytap.music",
    "小猿口算": "com.fenbi.android.leo",
    "MOMO陌陌": "com.immomo.momo",
    "支付宝": "com.eg.android.AlipayGphone",
    "爱奇艺": "com.qiyi.video",
    "DataCollection": "com.example.datacollection",
    "番茄畅听": "com.xs.fm",
    "语音翻译": "com.coloros.translate",
    "无线耳机": "com.oplus.melody",
    "得物": "com.shizhuang.duapp",
    "西瓜视频": "com.ss.android.article.video",
    "网易新闻": "com.netease.newsreader.activity",
    "腾讯视频": "com.tencent.qqlive",
    "淘宝特价版": "com.taobao.litetao",
    "七猫免费小说": "com.kmxs.reader",
    "自如": "com.ziroom.ziroomcustomer",
    "爱奇艺极速版": "com.qiyi.video.lite",
    "淘宝": "com.taobao.taobao",
    "斗鱼": "air.tv.douyu.android",
    "快手": "com.smile.gifmaker",
    "扫描全能王": "com.intsig.camscanner",
    "买单吧": "com.bankcomm.maidanba",
    "飞连": "com.volcengine.corplink",
    "菜鸟": "com.cainiao.wireless",
    "盒马": "com.wudaokou.hippo",
    "阿里巴巴": "com.alibaba.wireless",
    "智能家居": "com.heytap.smarthome",
    "小布指令": "com.coloros.shortcuts",
    "闲鱼": "com.taobao.idlefish",
    "游戏中心": "com.nearme.gamecenter",
    "搜狗输入法": "com.sohu.inputmethod.sogou",
    "QQ邮箱": "com.tencent.androidqqmail",
    "百度网盘": "com.baidu.netdisk",
    "QC浏览器": "com.fjhkf.gxdsmls",
    "酷安": "com.coolapk.market",
    "QQ音乐": "com.tencent.qqmusic",
    "百度": "com.baidu.searchbox",
    "抖音极速版": "com.ss.android.ugc.aweme.lite",
    "铁路12306": "com.MobileTicket",
    "OPPO商城": "com.oppo.store",
    "自由收藏": "com.coloros.favorite",
    "我的OPPO": "com.oplus.member",
    "掌阅": "com.chaozh.iReaderFree",
    "腾讯会议": "com.tencent.wemeet.app",
    "企业微信": "com.tencent.wework",
    "健康": "com.heytap.health",
    "微信": "com.tencent.mm",
    "京东": "com.jingdong.app.mall",
    "肯德基": "com.yek.android.kfc.activitys",
    "搜狐视频": "com.sohu.sohuvideo",
    "百度地图": "com.baidu.BaiduMap",
    "山姆会员商店": "cn.samsclub.app",
    "大麦": "cn.damai",
    "醒图": "com.ss.android.picshow",
    "设置": "com.android.settings",
    "王者荣耀": "com.tencent.tmgp.sgame",
    "随手记": "com.mymoney",
    "钢琴块二": "com.cmplay.tiles2_cn",
    "麦当劳": "com.mcdonalds.gma.cn",
    "寻艺": "com.vlinkage.xunyee",
    "京东到家": "com.jingdong.pdj",
    "小象超市": "com.meituan.retail.v.android",
    "京东金融": "com.jd.jrapp",
    "猫眼": "com.sankuai.movie",
    "红果免费短剧": "com.phoenix.read",
    "三角洲行动": "com.tencent.tmgp.dfm",
    "航旅纵横": "com.umetrip.android.msky.app",
    "淘票票": "com.taobao.movie.android",
    "学习强国": "cn.xuexi.android",
    "小米商城": "com.xiaomi.shop",
    "浏览器": "com.android.browser",
    "look": "com.vision.haokan",
    "什么值得买": "com.smzdm.client.android",
    "妙兜": "com.agent.miaodou",
    "瑞幸咖啡": "com.lucky.luckyclient",
    "豆瓣阅读": "com.douban.book.reader",
    "钉钉": "com.alibaba.android.rimet",
    "达美乐披萨": "com.android.permissioncontroller",
    "同程旅行": "com.tongcheng.android",
    "opentracks": "de.dennisguse.opentracks",
    "simple sms messenger": "com.simplemobiletools.smsmessenger",
    "joplin": "net.cozic.joplin",
    "miniwob": "com.google.androidenv.miniwob",
    "simple gallery pro": "com.simplemobiletools.gallery.pro",
    "simple gallery": "com.simplemobiletools.gallery.pro",
    "gallery": "com.simplemobiletools.gallery.pro",
    "audio recorder": "com.dimowner.audiorecorder",
    "broccoli": "com.flauschcode.broccoli",
    "simple calendar pro": "com.simplemobiletools.calendar.pro",
    "simple draw pro": "com.simplemobiletools.draw.pro",
    "draw": "com.simplemobiletools.draw.pro",
    "clipper": "ca.zgrs.clipper",
    "retro music": "code.name.monkey.retromusic",
    "arduia pro expense": "com.arduia.expense",
    "markor": "net.gsantner.markor",
    "tasks": "org.tasks",
    "osmAnd": "net.osmand",
    "给到": "com.guanaitong",
    "百词斩": "com.jiongji.andriod.card",
}


def _find_package_name_gelab_zero(app_name: str) -> str | None:
    """Mirror GELab-Zero `find_package_name` (difflib fuzzy match)."""
    import difflib

    app_name_lowered = (app_name or "").lower()
    package_name = GELAB_PACKAGE_NAME_MAP.get(app_name_lowered, None)

    max_match = {"name": None, "score": 0.0}
    if package_name is None:
        for key in GELAB_PACKAGE_NAME_MAP.keys():
            score = difflib.SequenceMatcher(None, app_name_lowered, key.lower()).ratio()
            if score > max_match["score"]:
                max_match["name"] = key
                max_match["score"] = score

        if max_match["name"] is None:
            return None
        package_name = GELAB_PACKAGE_NAME_MAP[max_match["name"]]

    return package_name


def find_package_name(app_name: str, protocol: str = "universal") -> str | None:
    """
    Find package name for an app.

    Args:
        app_name: App name (Chinese or English)
        protocol: "universal" | "autoglm" | "gelab"

    Returns:
        Package name or None if not found
    """
    protocol = (protocol or "universal").lower()

    if protocol == "autoglm":
        return AUTOGLM_APP_PACKAGES.get(app_name)

    if protocol == "gelab":
        return _find_package_name_gelab_zero(app_name)

    return _find_package_name_universal(app_name)


def _find_package_name_universal(app_name: str) -> str | None:
    """Universal / backward-compatible package name resolver."""
    # Normalize name
    name_lower = (app_name or "").lower().strip()

    # Remove common suffixes/prefixes
    name_lower = name_lower.replace(" ", "_")
    for suffix in ["app", "应用", "软件"]:
        name_lower = name_lower.replace(suffix, "")

    # Direct lookup
    if name_lower in APP_PACKAGE_MAP:
        return APP_PACKAGE_MAP[name_lower]

    # Check if it's already a package name
    if "." in name_lower and name_lower.count(".") >= 2:
        return app_name

    # Alias lookup
    if name_lower in APP_ALIASES:
        canonical = APP_ALIASES[name_lower]
        return APP_PACKAGE_MAP.get(canonical)

    # Fuzzy matching - check if name is substring
    for key, package in APP_PACKAGE_MAP.items():
        if name_lower in key or key in name_lower:
            return package

    # Chinese name mapping
    chinese_map = {
        "微信": "com.tencent.mm",
        "微博": "com.sina.weibo",
        "钉钉": "com.alibaba.android.rimet",
        "飞书": "com.ss.android.lark",
        "淘宝": "com.taobao.taobao",
        "京东": "com.jingdong.app.mall",
        "拼多多": "com.xunmeng.pinduoduo",
        "闲鱼": "com.taobao.idlefish",
        "美团": "com.sankuai.meituan",
        "饿了么": "me.ele",
        "大众点评": "com.dianping.v1",
        "高德地图": "com.autonavi.minimap",
        "百度地图": "com.baidu.BaiduMap",
        "滴滴": "com.sdu.didi.psnger",
        "携程": "ctrip.android.view",
        "抖音": "com.ss.android.ugc.aweme",
        "快手": "com.smile.gifmaker",
        "哔哩哔哩": "tv.danmaku.bili",
        "B站": "tv.danmaku.bili",
        "腾讯视频": "com.tencent.qqlive",
        "优酷": "com.youku.phone",
        "爱奇艺": "com.qiyi.video",
        "网易云音乐": "com.netease.cloudmusic",
        "QQ音乐": "com.tencent.qqmusic",
        "酷狗": "com.kugou.android",
        "喜马拉雅": "com.ximalaya.ting.android",
        "小红书": "com.xingin.xhs",
        "知乎": "com.zhihu.android",
        "豆瓣": "com.douban.frodo",
        "支付宝": "com.eg.android.AlipayGphone",
        "云闪付": "com.unionpay",
        "菜鸟": "com.cainiao.wireless",
        "设置": "com.android.settings",
        "相机": "com.android.camera",
        "相册": "com.android.gallery3d",
        "计算器": "com.android.calculator2",
        "时钟": "com.android.deskclock",
        "日历": "com.android.calendar",
        "通讯录": "com.android.contacts",
        "短信": "com.android.mms",
        "电话": "com.android.dialer",
        "文件": "com.android.documentsui",
    }

    return chinese_map.get(app_name)


def get_all_supported_apps() -> list[str]:
    """Get list of all supported app names."""
    apps = list(APP_PACKAGE_MAP.keys())
    apps.sort()
    return apps
