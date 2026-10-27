# coding=utf-8
"""
电影侠 (dyxia / hhkan.tv)  | TVBox Python 爬虫 
==============================================================
融合三条链路，任一可用即能出结果：

  A. API 线（主路）  —— libjake.so 逆向出的 .capi 协议
       AES-256-CBC 响应解密 + HMAC-SHA1 请求签名 + 域名池轮换
  B. 网页线（备用）  —— www.dyx00.com HTML 解析
       v-item 卡片 / detail-info-row / play 页 playSource
  C. 番外线（直连）  —— 豆花式 PoW 挑战 + box master m3u8 拆子流

关键点
  - Accept-Encoding: identity 必须带，否则密文被 gzip 解不开
  - 签名源里 query 用解码原文，URL 里用编码形式
  - CDN 302 调度：请求原节点对分片只回 3 字节 "OK\n"，必须走重定向后节点
"""
import base64
import hashlib
import hmac as hmaclib
import json
import random
import re
import socket
import string
import sys
import threading
import time
import unicodedata
import urllib.parse
from urllib.parse import quote, unquote, urljoin, urlparse

sys.path.append('..')

try:
    import requests
except ImportError:
    requests = None

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    class _BaseSpider(object):
        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                import requests as _rq
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=20, pool_maxsize=20, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, **kw):
            t = kw.pop('timeout', 20)
            r = self._sess.get(url, headers=headers, timeout=t, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[dyx]", *a)
            except Exception:
                pass

    Spider = _BaseSpider

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except ImportError:
    try:
        from Cryptodome.Cipher import AES
        from Cryptodome.Util.Padding import unpad
    except ImportError:
        AES = None
        unpad = None


# ══════════════════════════ 常量 ══════════════════════════

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ---- API 线（逆向所得）----
_AES_KEY = b"ayt5wy5afwmwrpb1" + b"9k9s3psx3dymyd0n"
_AES_IV = b"b3t069ijy7pirw0j"
_MAC_KEY = b"ksggsr4tp6difdo1c3im8fqd3g"

_PKG = "com.dyxiaD13962260701.t005905"
_APP_ID = "dyxia"
_API_UA = "okhttp/4.12.0"

# 签名参与项，顺序敏感
_SIGN_KEYS = ["appId", "deviceCreatedAt", "deviceId", "st", "userId"]

# 引导域名：只用于第一次拉 appInit，成功后用服务端下发的池覆盖
_BOOTSTRAP_HOSTS = [
    "https://vcache.qvfic.com",
    "https://vcache.zwtlzch.cn",
    "https://vcache.mjrlin.cn",
    "https://vcache.kvod14.com",
    "https://vcache.shkjbd.com",
    "https://vcache.srnffc.cn",
    "https://vcache.ybsdkl.cn",
    "https://43.248.100.71:51020",
]


# ---- 网页线 ----
WEB_HOST = "https://www.dyx00.com"
WEB_PIC_CDN = "https://vres.cyscyy.com"
WEB_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
WEB_SKIP = ('搜索', '百度', '搜狗', '神马', '360', 'baidu', 'google',
            'sogou', 'kuaishou', '快手')
WEB_WM = ('kkys', 'kekys', '可可影视')

# ---- 番外线 ----
BOX_HOST = "https://box.dyrs.com.de"

_LINE_PRIORITY = ["vip", "1080zyk", "wztv", "bfzym3u8", "dyttm3u8",
                  "ffm3u8", "lzm3u8", "modum3u8", "jsm3u8", "mtm3u8"]
_LINE_ALIAS = {
    "vip": "VIP线路", "modum3u8": "魔都M3U8", "jsm3u8": "极速M3U8",
    "mtm3u8": "茅台M3U8", "1080zyk": "1080资源", "lzm3u8": "量子M3U8",
    "bfzym3u8": "暴风资源", "dyttm3u8": "电影天堂", "ffm3u8": "非凡M3U8",
    "wztv": "王者TV",
}


# ══════════════════════════ 正则 ══════════════════════════

# 网页线：卡片
_RE_VITEM = re.compile(
    r'<a[^>]*href="(/detail/(\d+)\.html)"[^>]*class="v-item"[^>]*>(.*?)</a>',
    re.S)
_RE_VITEM_TITLE = re.compile(
    r'class="v-item-title[^"]*"[^>]*>(.*?)</div>', re.S)
_RE_VITEM_BOTTOM = re.compile(
    r'class="v-item-bottom"[^>]*>(.*?)</div>', re.S)
_RE_IMG_ORIGIN = re.compile(
    r'data-original="([^"]+\.(?:jpg|png|webp|jpeg)[^"]*)"', re.I)

# 网页线：搜索
_RE_SEARCH_ITEM = re.compile(
    r'<a[^>]*href="(/detail/(\d+)\.html)"[^>]*class="search-result-item"'
    r'[^>]*>(.*?)</a>', re.S)
_RE_SEARCH_TITLE = re.compile(
    r'class="[^"]*search-result-item-title[^"]*"[^>]*>(.*?)</div>', re.S)
_RE_SEARCH_FOOT = re.compile(
    r'class="search-result-item-footer"[^>]*>(.*?)</div>', re.S)

# 网页线：详情
_RE_DETAIL_TITLE = re.compile(
    r'class="detail-title"[^>]*>(.*?)</div>', re.S)
_RE_STRONG = re.compile(r'<strong[^>]*>(.*?)</strong>', re.S)
_RE_INFO_ROW = re.compile(
    r'class="detail-info-row"[^>]*>.*?class="detail-info-row-side"[^>]*>(.*?)</div>'
    r'.*?class="detail-info-row-main"[^>]*>(.*?)</div>', re.S)
_RE_META_DESC = re.compile(
    r'<meta\s+name="description"\s+content="([^"]*)"', re.I)

# 番外线：剧集 / 播放
_RE_EPISODE_A = re.compile(r'<a\s+href="([^"]+)"([^>]*?)>(.*?)</a>', re.S | re.I)
_RE_DATA_ORIGIN = re.compile(r'data-origin="([^"]+)"', re.I)
_RE_DATA_TITLE = re.compile(r'data-title="([^"]+)"', re.I)
_RE_BTN_TITLE = re.compile(r'<button[^>]*>([^<]+)</button>', re.I)
_RE_SOURCE_ITEM = re.compile(
    r'<a[^>]*class="source-item[^"]*"[^>]*>(.*?)</a>', re.S)
_RE_EPISODE_LIST = re.compile(
    r'<div class="episode-list"[^>]*>(.*?)</div>', re.S)

_RE_PLAYER_AA = re.compile(r"aa\s*:\s*JSON\.parse\('(.*?)'\)", re.S)
_RE_PLAY_SRC = re.compile(
    r'playSource\s*=\s*\{[\s\S]*?src:\s*"([^"]+)"')
_RE_PLAY_SRC2 = re.compile(
    r'playSource\s*\.\s*src\s*=\s*["\']([^"\']+)["\']')
_RE_M3U8_ANY = re.compile(
    r'src\s*:\s*["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', re.I)

_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_PIC_ID = re.compile(r'/img/id/[A-Za-z0-9]+\.(?:jpg|png|webp)', re.I)

# 豆花式卡片（番外线备用）
_RE_CARD = re.compile(
    r'href="(/(?:movie|tv)/[^"]+?\.html)[^"]*"[^>]*>'
    r'[\s\S]{0,200}?'
    r'<img[^>]*?alt="([^"]*)"[^>]*?(?:data-src|src)="([^"]*)"',
    re.S | re.I)
_RE_INTRO = re.compile(
    r'<span\s+class="font-bold text-\[#ff3347\] mr-1">简介:</span>\s*'
    r'([\s\S]*?)</div>', re.S | re.I)
_RE_DIRECTOR = re.compile(
    r'<span\s+class="text-\[#2e2e2e\]\s+font-bold">导演</span>\s*'
    r'<span[^>]*>([^<]*)</span>', re.S | re.I)
_RE_ACTOR = re.compile(
    r'<span\s+class="text-\[#2e2e2e\]\s+font-bold">主演</span>\s*'
    r'<span[^>]*>([\s\S]*?)</span>', re.S | re.I)

# PoW 挑战页特征
_RE_POW_HASH = re.compile(r"var\s+hash\s*=\s*['\"]([a-f0-9]{40})['\"]")
_RE_POW_TARGET = re.compile(r"var\s+target\s*=\s*['\"]([a-f0-9]{40})['\"]")


# ══════════════════════════ 分类 / 过滤器 ══════════════════════════

_CLASSES = [
    {"type_id": "ch:1", "type_name": "电影"},
    {"type_id": "ch:2", "type_name": "剧集"},
    {"type_id": "ch:3", "type_name": "动漫"},
    {"type_id": "ch:4", "type_name": "综艺纪录"},
    {"type_id": "ch:6", "type_name": "短剧"},
    {"type_id": "netflix:1000", "type_name": "Netflix"},
    {"type_id": "new", "type_name": "今日更新"},
]

_SORTS = [{"n": "最新", "v": "latest"},
          {"n": "最热", "v": "hot"},
          {"n": "评分", "v": "score"}]
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "中国大陆", "v": "中国大陆"}, {"n": "美国", "v": "美国"},
    {"n": "日本", "v": "日本"}, {"n": "英国", "v": "英国"},
    {"n": "中国香港", "v": "中国香港"}, {"n": "法国", "v": "法国"},
    {"n": "韩国", "v": "韩国"}, {"n": "加拿大", "v": "加拿大"},
    {"n": "印度", "v": "印度"}, {"n": "德国", "v": "德国"},
    {"n": "意大利", "v": "意大利"}, {"n": "中国台湾", "v": "中国台湾"},
]
_LANGS = [
    {"n": "全部", "v": ""},
    {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"},
    {"n": "日语", "v": "日语"}, {"n": "韩语", "v": "韩语"},
    {"n": "粤语", "v": "粤语"},
]

_GENRE = {
    "1": ["全部", "剧情", "喜剧", "动作", "爱情", "惊悚", "犯罪", "恐怖",
          "悬疑", "冒险", "奇幻", "科幻", "院线", "家庭", "历史", "战争",
          "纪录片", "古装", "音乐", "动画", "传记", "武侠", "运动", "西部", "短片"],
    "2": ["全部", "剧情", "喜剧", "爱情", "犯罪", "悬疑", "家庭", "古装",
          "惊悚", "动作", "奇幻", "科幻", "都市", "历史", "战争", "冒险",
          "武侠", "恐怖", "青春", "传记", "谍战", "情感", "纪录", "军旅", "时装"],
    "3": ["全部", "动画", "冒险", "喜剧", "奇幻", "剧情", "科幻", "动作",
          "儿童", "悬疑", "都市", "家庭", "国漫", "日常", "爱情", "玄幻",
          "日漫", "音乐", "治愈", "短片", "古风", "犯罪", "武侠", "运动", "校园"],
    "4": ["全部", "真人秀", "脱口秀", "国产综艺", "喜剧", "晚会", "综艺",
          "音乐", "纪录", "游戏", "生活", "港台综艺", "日韩综艺", "剧情",
          "文化", "相声", "情感", "悬疑", "欧美综艺", "美食", "竞技"],
    "6": ["全部", "AI漫剧", "短剧", "剧情", "爱情", "爽文", "古装", "短片",
          "悬疑", "喜剧", "奇幻", "都市", "玄幻", "犯罪", "家庭", "穿越",
          "惊悚", "武侠", "科幻", "动作", "冒险", "恐怖", "青春", "历史"],
}

_FILTERS = {}
for _c in _CLASSES:
    _cid = _c["type_id"].split(":", 1)[-1]
    if ":" not in _c["type_id"]:
        continue
    _FILTERS[_c["type_id"]] = [
        {"key": "category", "name": "分类",
         "value": [{"n": x, "v": "" if x == "全部" else x}
                   for x in _GENRE.get(_cid, ["全部"])]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "language", "name": "语言", "value": _LANGS},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]


# ══════════════════════════ 主类 ══════════════════════════

class Spider(Spider):

    # 图片域名缓存（跨实例）
    _img_base_cache = {}
    _IMG_BASE_TTL = 1800
    _IMG_FALLBACK = {
        "vod1": "https://103.39.111.180:51050/vod1",
        "units": "https://103.39.111.180:51050/vod1",
        "sres": "https://103.39.111.180:51051/vod1",
    }

    # 类级默认值：未 init() 时也不至于 AttributeError
    site_url = WEB_HOST
    sion_id = "6ac4b6643b9fea31774d1157"
    default_pic = WEB_HOST + "/template/douhua/douhua.me.png"
    host = _BOOTSTRAP_HOSTS[0]
    host_logic = "https://vlogic.qvfic.com"
    timeout = 20
    headers = {"User-Agent": WEB_UA, "Referer": WEB_HOST + "/"}
    _play_cache = {}
    _token = ""
    _token_t = 0
    _host_pool = []
    img_groups = {}
    channel_query = {}
    vod_tabs = []
    src_headers = {}

    def getName(self):
        return "电影侠"

    # ═══════════════ 初始化 ═══════════════
    def init(self, extend=""):
        self.sess = self._sess
        self.sess.trust_env = False
        self.sess.verify = False
        self.timeout = 20

        self.host = _BOOTSTRAP_HOSTS[0]
        self.host_logic = "https://vlogic.qvfic.com"
        self._host_pool = []

        # 设备指纹
        self.device_id = "".join(random.choice(string.hexdigits.lower())
                                 for _ in range(32))
        self.device_created_at = str(int(time.time() * 1000))
        self.user_id = ""
        self.user_token = ""
        self.user_created_at = ""

        # appInit 填充
        self.vod_tabs = []
        self.channel_query = {}
        self.img_groups = {}
        self.src_headers = {}

        self._home_cache = None
        self._home_ts = 0
        self._play_cache = {}
        self._api_ok = False
        self._warmed = False

        # ---- 番外线（网页 HTML）----
        self.site_url = WEB_HOST
        self.sion_id = "6ac4b6643b9fea31774d1157"
        self.default_pic = WEB_HOST + "/template/douhua/douhua.me.png"
        self.headers = {
            "User-Agent": WEB_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }

        # extend 支持：https://域名 / proxy=7897 / 纯端口 / site=xxx
        if extend:
            for p in re.split(r"[,，;\s]+", extend or ""):
                p = (p or "").strip()
                if not p:
                    continue
                if p.startswith("proxy=") or p.isdigit():
                    port = p.split("=", 1)[1].strip() if p.startswith("proxy=") else p
                    if port.isdigit():
                        self.sess.proxies = {
                            "http": "http://127.0.0.1:%s" % port,
                            "https": "http://127.0.0.1:%s" % port,
                        }
                        self.log("使用代理 127.0.0.1:%s" % port)
                elif p.startswith("site="):
                    self.site_url = p.split("=", 1)[1].strip().rstrip("/")
                    self.headers["Referer"] = self.site_url + "/"
                elif p.startswith("http"):
                    self.host = p.rstrip("/")

        self._init_app()
        self.log("init: api=%s host=%s" % ("OK" if self._api_ok else "FAIL", self.host))

    # ═══════════════ 基础工具 ═══════════════
    def log(self, *a, **kw):
        try:
            print("[dyx]", *a)
        except Exception:
            pass

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = unicodedata.normalize("NFKC", s)
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.site_url + url
        return urllib.parse.urljoin(self.site_url + "/", url)

    def _is_wm(self, s):
        t = (s or "").lower()
        return any(w in t for w in WEB_WM)

    @staticmethod
    def _label_text(v):
        """字段可能是 str / list[dict] / dict，统一成可读文本。"""
        if not v:
            return ""
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            return str(v.get("name") or v.get("id") or "")
        if isinstance(v, list):
            return ",".join(str(x.get("name") or x) if isinstance(x, dict) else str(x)
                            for x in v)
        return str(v)

    # ═══════════════ API 线：签名与加解密 ═══════════════
    def _headers(self):
        h = {
            "User-Agent": _API_UA,
            "Accept-Encoding": "identity",     # 必须，否则密文无法解密
            "appId": _APP_ID,
            "os": "android",
            "appVersion": "3.5.0",
            "sdkVersion": "0.2.0",
            "package": _PKG,
            "channelId": "v1",
            "st": "1",
            "deviceId": self.device_id,
            "deviceCreatedAt": self.device_created_at,
            "deviceInfo": "android",
            "X-CDN": "1",
        }
        if self.user_id:
            h["X-USER"] = "1"
            h["userId"] = self.user_id
            h["userCreatedAt"] = self.user_created_at or "0"
            h["X-Token"] = self.user_token or ""
        return h

    def _sign(self, method, path, pairs, headers, ts):
        """HMAC-SHA1 签名。

        签名源 = method | path | query(原文) | TS | 关键header | ""
        注意：query 用原文（不 URL 编码）；多参数需排序。
        """
        items = ["%s=%s" % (k, v) for k, v in pairs]
        if len(items) > 1:
            items = sorted(items)
        qs = "&".join(items)
        hdr = "&".join("%s=%s" % (k, headers[k]) for k in _SIGN_KEYS if headers.get(k))
        src = "%s|%s|%s|%s|%s|" % (method.lower(), path, qs, ts, hdr)
        return hmaclib.new(_MAC_KEY, src.encode("utf-8"), hashlib.sha1).hexdigest()

    @staticmethod
    def _decrypt(raw):
        if not raw or len(raw) % 16 != 0 or AES is None:
            return None
        try:
            pt = unpad(AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV).decrypt(raw), 16)
        except Exception:
            return None
        try:
            return json.loads(pt.decode("utf-8"))
        except Exception:
            return None

    def _api(self, path, params=None, host=None, method="GET", raw_ok=False, body=None):
        """带签名的 .capi 请求。raw_ok=True 返回解密后完整 JSON。"""
        pairs = []
        if params:
            for k, v in params.items():
                if v is not None and v != "":
                    pairs.append((k, str(v)))
        hdrs = self._headers()
        ts = str(int(time.time() * 1000))
        hdrs["TS"] = ts
        hdrs["sign"] = self._sign(method, path, pairs, hdrs, ts)

        # 域名池轮换兜底
        if host:
            candidates = [host]
        else:
            candidates = [self.host]
            for h in (self._host_pool or []):
                if h and h not in candidates:
                    candidates.append(h)
            candidates = candidates[:3]

        for cand in candidates:
            url = (cand or self.host).rstrip("/") + path
            if pairs:
                url += "?" + "&".join("%s=%s" % (k, quote(v, safe="")) for k, v in pairs)
            try:
                if method == "POST":
                    r = self.sess.post(url, headers=hdrs, data=body or "",
                                       timeout=self.timeout)
                else:
                    r = self.sess.get(url, headers=hdrs, timeout=self.timeout)
            except Exception:
                continue
            j = self._decrypt(r.content)
            if not j:
                continue
            if not host and cand != self.host:
                self.host = cand
                self.log("切换域名 -> %s" % cand)
            if raw_ok:
                return j
            if j.get("code") not in (200, "200"):
                return None
            return j.get("data")
        return None

    def _init_app(self):
        """引导初始化：按顺序试域名，第一个能返回 appInit 的就用。"""
        order = []
        for h in [self.host] + _BOOTSTRAP_HOSTS:
            h = (h or "").rstrip("/")
            if h and h not in order:
                order.append(h)
        old_to = self.timeout
        self.timeout = 8
        ok = False
        try:
            for h in order:
                j = self._api("/v5/config/appInit.capi", host=h, raw_ok=True)
                if j and "urls" in j:
                    self.host = h
                    self._apply_init(j)
                    ok = True
                    self.log("appInit OK -> %s" % h)
                    break
        finally:
            self.timeout = old_to
        self._api_ok = ok
        if not ok:
            self.log("appInit 失败：所有引导域名均不可用，走网页线")
        return ok

    def _apply_init(self, j):
        """应用 appInit 配置：域名池 + 图片组 + 分类 + 匿名会话。"""
        urls = j.get("urls") or {}
        caches = [u for u in (urls.get("cache") or []) if u]
        logics = [u for u in (urls.get("logic") or []) if u]

        pool = []
        for h in [self.host] + caches:
            h = (h or "").rstrip("/")
            if h and h not in pool:
                pool.append(h)
        self._host_pool = pool
        if pool:
            self.host = pool[0]
        if logics:
            self.host_logic = logics[0]

        for g in (j.get("groups") or []):
            gid = g.get("id")
            doms = [d.get("domain") for d in (g.get("url") or []) if d.get("domain")]
            if gid and doms:
                self.img_groups[gid] = doms

        self.vod_tabs = j.get("vodTabs") or []

        cq = {}
        for item in (j.get("channelListQuery") or []):
            cid = item.get("channelId")
            q = {}
            for it in (item.get("items") or []):
                q[it.get("query")] = [x.get("id") for x in (it.get("data") or [])]
            if cid is not None:
                cq[str(cid)] = q
        self.channel_query = cq

        for sh in (j.get("sourceHeader") or []):
            sid = sh.get("siteId")
            if sid:
                self.src_headers[sid] = sh.get("header") or {}

        self._anon_login()

    def _anon_login(self):
        """POST /user/anonymous -> {id, token, ...}（搜索等接口需要会话）"""
        try:
            j = self._api("/user/anonymous", method="POST", raw_ok=True, body="")
            d = (j or {}).get("data") or {}
            uid = d.get("id")
            tok = d.get("token")
            if uid and tok:
                self.user_id = str(uid)
                self.user_token = str(tok)
                self.user_created_at = str(d.get("createdAt") or self.device_created_at)
        except Exception:
            pass

    # ═══════════════ 图片地址 ═══════════════
    def _pick_base(self, group, groups):
        """选图片域名：国内 .cn 镜像 > 纯 IP > 海外域名，带 TTL 缓存。"""
        hit = Spider._img_base_cache.get(group)
        if hit and time.time() - hit[1] < Spider._IMG_BASE_TTL:
            return hit[0]

        doms = groups.get(group) or []
        pool, seen = [], set()
        for d in doms:
            d = str(d).rstrip("/")
            if d and d not in seen:
                seen.add(d)
                pool.append(d)
        if not pool:
            pool = [Spider._IMG_FALLBACK.get(group, "https://vres.mppcdrr.cn/vod1")]

        cn, raw_ip, other = [], [], []
        for d in pool:
            try:
                host = urlparse(d).hostname
            except Exception:
                continue
            if not host:
                continue
            try:
                socket.getaddrinfo(host, None)
            except Exception:
                continue
            if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
                raw_ip.append(d)
            elif host.endswith(".cn"):
                cn.append(d)
            else:
                other.append(d)

        if not cn:
            # 本组无国内域名：借其它组的 .cn 镜像（同一套存储树，实测通用）
            for _, odoms in (groups or {}).items():
                for d in (odoms or []):
                    d = str(d).rstrip("/")
                    try:
                        host = urlparse(d).hostname
                    except Exception:
                        continue
                    if not host or not host.endswith(".cn") or d in cn:
                        continue
                    try:
                        socket.getaddrinfo(host, None)
                    except Exception:
                        continue
                    cn.append(d)

        chosen = (cn or raw_ip or other or pool)[0]
        Spider._img_base_cache[group] = (chosen, time.time())
        return chosen

    def _pic(self, path, group=None, groups=None):
        """拼接图片地址。groups 的 domain 已含完整前缀，只需 base + path。"""
        if not path:
            return ""
        if path.startswith("//"):
            return "https:" + path
        if path.startswith("http"):
            return path
        group = group or "vod1"
        if not path.startswith("/"):
            path = "/" + path
        base = self._pick_base(group, groups if groups is not None else self.img_groups)
        return base + path

    # ═══════════════ 分类 ═══════════════
    def _classes(self):
        """分类列表。优先用 appInit 下发的 vodTabs，失败退回内置表。"""
        out = []
        for t in (self.vod_tabs or []):
            name = t.get("text")
            cid = t.get("channelId")
            typ = (t.get("type") or "category").lower()
            if not name or cid is None:
                continue
            if typ == "home":              # 壳子自带推荐，跳过
                continue
            if typ == "netflix":
                out.append({"type_id": "netflix:%s" % cid, "type_name": str(name)})
            else:
                out.append({"type_id": "ch:%s" % cid, "type_name": str(name)})
        if out:
            out.append({"type_id": "new", "type_name": "今日更新"})
            return out
        return list(_CLASSES)

    def homeContent(self, filter=False):
        result = {"class": self._classes(), "filters": {}}
        filters = {}
        for tid, q in (self.channel_query or {}).items():
            opts = []
            for key, ids in q.items():
                if not ids:
                    continue
                vals = [{"n": i if i else "全部", "v": i}
                        for i in ids[:40] if i is not None]
                if vals:
                    opts.append({"key": key, "name": key, "value": vals})
            if opts:
                filters["ch:%s" % tid] = opts
        # appInit 没给过滤器时用内置表兜底，保证筛选栏不空
        for c in result["class"]:
            if c["type_id"] not in filters and c["type_id"] in _FILTERS:
                filters[c["type_id"]] = _FILTERS[c["type_id"]]
        result["filters"] = filters
        return result

    # ═══════════════ 首页 ═══════════════
    def _home(self):
        if self._home_cache and time.time() - self._home_ts < 300:
            return self._home_cache
        d = self._api("/v6/vod/home.capi")
        if d:
            self._home_cache = d
            self._home_ts = time.time()
        return self._home_cache or {}

    def _vod(self, it):
        if not isinstance(it, dict):
            return None
        vid = it.get("id")
        title = it.get("title")
        if vid is None or not title:
            return None
        bits = []
        for k in ("topRightLabel", "topLeftLabel", "bottomLabel"):
            v = it.get(k)
            if isinstance(v, str) and v.strip():
                bits.append(v.strip())
        labels = it.get("labels")
        if isinstance(labels, list):
            for lb in labels[:2]:
                if isinstance(lb, dict) and lb.get("name"):
                    bits.append(str(lb["name"]))
        if it.get("playCount"):
            bits.append("%s次播放" % it["playCount"])
        if it.get("score"):
            bits.append("%s分" % it["score"])
        return {
            "vod_id": str(vid),
            "vod_name": self._clean(str(title)),
            "vod_pic": self._pic(it.get("imagePath") or "",
                                 it.get("imageGroup") or "vod1", self.img_groups),
            "vod_year": Spider._label_text(it.get("year")),
            "vod_remarks": " · ".join(bits[:3]),
        }

    def homeVideoContent(self):
        # 主线：API 首页
        d = self._home()
        out, seen = [], set()
        for blk in (d.get("blocks") or []):
            for it in (blk.get("data") or []):
                v = self._vod(it)
                if v and v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    out.append(v)
        if out:
            return {"list": out[:80]}

        # 备用：网页首页
        self.log("首页走网页线")
        html = self._page(self.site_url + "/")
        return {"list": self._parse_web_items(html)}

    # ═══════════════ 分类内容 ═══════════════
    def categoryContent(self, tid, pg, filter=False, extend=None):
        tid = str(tid)
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        ex = extend if isinstance(extend, dict) else {}
        for k in list(ex.keys()):
            if ex[k] in ("", None, "全部"):
                del ex[k]

        videos, seen = [], set()
        pagecount = 1

        if tid == "new":
            # 今日更新走网页线（API 无对应接口）
            html = self._page("%s/new/%d.html" % (self.site_url, page), timeout=15)
            videos = self._parse_web_items(html)
            return {"list": videos, "page": page, "pagecount": 999,
                    "limit": 24, "total": 99999}

        if tid.startswith("netflix:"):
            d = self._api("/v2/vod/netflixNewWatch.capi")
            for blk in ((d or {}).get("items") or []):
                for it in (blk.get("data") or []):
                    v = self._vod(it)
                    if v and v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        videos.append(v)
            pagecount = 1

        elif tid.startswith("ch:") or tid.startswith("category:"):
            cid = tid.split(":", 1)[1]
            params = {"channelId": cid, "sort": ex.get("sort") or "latest"}
            for k in ("category", "year", "area", "language"):
                if ex.get(k):
                    params[k] = ex[k]
            if page > 1:
                params["next"] = "page=%d" % page

            d = self._api("/vod/channel/list.capi", params)

            if d:
                want = {k: ex.get(k) for k in ("category", "year", "area", "language")
                        if ex.get(k)}
                for it in (d.get("items") or []):
                    v = self._vod(it)
                    if not v:
                        continue
                    # 过滤必须客户端确认（服务端有时忽略）
                    if want:
                        labs = it.get("labels") or []
                        names = [str(x.get("name")) for x in labs
                                 if isinstance(x, dict)]
                        ok = True
                        for wk, wv in want.items():
                            if wk == "category" and wv and wv not in names:
                                ok = False
                            if wk == "year" and wv and str(it.get("year") or "") != str(wv):
                                ok = False
                        if not ok:
                            continue
                    if v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        videos.append(v)
                pagecount = 9999 if d.get("next") else page
            else:
                # 备用：网页频道页
                self.log("分类走网页线 tid=%s" % tid)
                q = {"page": page - 1, "sion_id": self.sion_id}
                if ex.get("category"):
                    q["class"] = ex["category"]
                if ex.get("year"):
                    q["year"] = ex["year"]
                if ex.get("area"):
                    q["area"] = ex["area"]
                html = self._page("%s/%s.html?%s" % (
                    self.site_url, tid.replace("ch:", ""),
                    urllib.parse.urlencode(q)), timeout=15)
                videos = self._parse_web_items(html)
                pagecount = self._page_count(html)

        elif tid == "ranking":
            d = self._api("/vod/rankingVods.capi",
                          {"rankingId": ex.get("rankingId") or "weekrank_dy"})
            for it in ((d or {}).get("items") or (d or {}).get("list") or []):
                v = self._vod(it)
                if v and v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    videos.append(v)

        elif tid == "topic":
            d = self._api("/v3/vod/specialTopics.capi")
            for it in ((d or {}).get("items") or (d or {}).get("list") or []):
                v = self._vod(it)
                if v and v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    videos.append(v)

        else:
            # 兜底：首页数据
            for blk in (self._home().get("blocks") or []):
                for it in (blk.get("data") or []):
                    v = self._vod(it)
                    if v and v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        videos.append(v)

        n = len(videos)
        return {
            "list": videos,
            "page": page,
            "pagecount": int(pagecount),
            "limit": n or 20,
            "total": int(n),
        }

    # ═══════════════ 详情 ═══════════════
    def detailContent(self, array):
        result = {"list": []}
        try:
            vid = array[0]
            if isinstance(vid, dict):
                vid = vid.get("vod_id") or vid.get("id")
            vid = str(vid)

            # 主线：API 详情
            j = self._api("/v2/vod/detail.capi", {"vodId": vid})
            if j and j.get("id"):
                return self._detail_api(vid, j)

            # 备用：网页详情
            self.log("详情走网页线 vid=%s" % vid)
            if re.match(r"^\d+$", vid):
                return self._detail_web(vid)
        except Exception as e:
            import traceback
            self.log("detailContent ERR: %s\n%s" % (e, traceback.format_exc()))
        return result

    def _detail_api(self, vid, j):
        content = (j.get("summary") or "").strip()
        content = INTRO_PREFIX + ("\n" + content if content else "")

        video = {
            "vod_id": vid,
            "vod_name": j.get("title") or "",
            "vod_pic": self._pic(j.get("imagePath") or "",
                                 j.get("imageGroup") or "vod1", self.img_groups),
            "type_name": j.get("channelName") or "",
            "vod_year": Spider._label_text(j.get("year")),
            "vod_area": Spider._label_text(j.get("area")),
            "vod_actor": Spider._label_text(j.get("actors")),
            "vod_director": Spider._label_text(j.get("directors")),
            "vod_remarks": j.get("scoreText") or (
                ("%s分" % j["score"]) if j.get("score") else ""),
            "vod_content": content,
        }

        froms, urls = [], []
        for src in (j.get("playSources") or []):
            eps = src.get("list") or []
            if not eps:
                continue
            ep_strs = []
            for ep in eps:
                token = "%s|%s|%s" % (vid, src.get("siteId") or "", ep.get("id") or "")
                ep_strs.append("%s$%s" % (ep.get("title") or "正片", token))
            if ep_strs:
                froms.append(src.get("name") or src.get("siteId") or "线路")
                urls.append("#".join(ep_strs))
        if urls:
            video["vod_play_from"] = "$$$".join(froms)
            video["vod_play_url"] = "$$$".join(urls)
        return {"list": [video]}

    def _detail_web(self, vid):
        """网页线详情：解析 detail 页 + play 页剧集分组。"""
        html = self._page("%s/detail/%s.html" % (self.site_url, vid))
        if not html:
            return {"list": []}

        vod = {"vod_id": vid}

        # 标题
        name = ""
        m = re.search(r'class="detail-title"[^>]*>(.*?)</div>', html, re.S)
        if m:
            parts = []
            for s in _RE_STRONG.findall(m.group(1)):
                c = self._clean(s)
                if c and not self._is_wm(c):
                    parts.append(c)
            name = "".join(parts).strip()
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        vod["vod_name"] = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vid

        # 封面
        pic = ""
        for im in _RE_IMG_ORIGIN.findall(html):
            pic = self._web_pic(im)
            if pic:
                break
        vod["vod_pic"] = pic or self.default_pic

        # 元信息
        vod["vod_remarks"] = vod["vod_year"] = vod["vod_area"] = ""
        vod["vod_director"] = vod["vod_actor"] = ""
        for label, cont in _RE_INFO_ROW.findall(html):
            label = self._clean(label)
            cont = self._clean(cont)
            if "导演" in label:
                vod["vod_director"] = re.sub(r"\s*\n\s*", " / ", cont)
            elif "演员" in label or "主演" in label:
                vod["vod_actor"] = re.sub(r"\s*\n\s*", " / ", cont)
            elif "备注" in label or "状态" in label:
                vod["vod_remarks"] = cont
            elif "地区" in label or "区域" in label:
                vod["vod_area"] = cont
            elif "年份" in label or "首映" in label or "上映" in label:
                # 首映常是 2026-09-30，只留年份
                ym = re.search(r"(19|20)\d{2}", cont)
                vod["vod_year"] = ym.group(0) if ym else cont
        if not vod["vod_remarks"]:
            m = re.search(r"vk-badge[^>]*>\s*([\d.]+)\s*<", html)
            if m:
                vod["vod_remarks"] = m.group(1) + "分"

        # 简介（多层兜底）
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(
                r'<div[^>]*class="[^"]*text-\[#555\][^"]*reset-style[^"]*"[^>]*>'
                r'([\s\S]*?)</div>', html, re.S)
            if m:
                content = self._clean(m.group(1))
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        vod["vod_content"] = INTRO_PREFIX + ("\n" + content if content else "")

        # 剧集：从 play 页拿分组
        links = list(dict.fromkeys(
            re.findall(r'href="(/play/%s-\d+-\d+\.html)"' % vid, html)))
        pf, pu = [], []
        if links:
            groups, order = self._web_episodes(links[0], vid)
            if groups:
                for origin in order:
                    pf.append(_LINE_ALIAS.get(origin, origin))
                    pu.append("#".join(groups[origin]))
            if not pf:
                pf.append("线路1")
                pu.append("#".join("第%d集$%s" % (i + 1, self.site_url + u)
                                   for i, u in enumerate(links)))
        vod["vod_play_from"] = "$$$".join(pf)
        vod["vod_play_url"] = "$$$".join(pu)
        return {"list": [vod]}

    def _web_episodes(self, first_link, vid):
        """解析 play 页剧集。

        返回 (groups, order)：
          groups[线路名] = ["集名$完整URL", ...]   —— 统一为已拼好的字符串
          order          = 线路名列表（已按蓝光优先排序）
        兼容有/无 data-title（短剧）。
        """
        groups, order = {}, []
        ph = self._page(self.site_url + first_link)
        if not ph:
            return groups, order

        names = []
        for it in _RE_SOURCE_ITEM.findall(ph):
            lb = re.search(r'source-item-label[^>]*>([^<]+)<', it)
            sb = re.search(r'source-item-sublabel[^>]*>([^<]+)<', it)
            lb = self._clean(lb.group(1)) if lb else ""
            sb = self._clean(sb.group(1)) if sb else ""
            names.append("%s(%s)" % (lb, sb) if lb and sb
                         else (lb or "线路%d" % (len(names) + 1)))

        epl = _RE_EPISODE_LIST.findall(ph)
        for i, el in enumerate(epl[:len(names)] if names else epl):
            nm = names[i] if i < len(names) else "线路%d" % (i + 1)
            if self._is_wm(nm) or any(k in nm.lower() for k in WEB_SKIP):
                continue
            eps = []
            for eu, ein in re.findall(
                    r'<a[^>]*href="(/play/\d+-\d+-\d+\.html)"[^>]*>(.*?)</a>',
                    el, re.S):
                en = self._clean(ein) or "第%d集" % (len(eps) + 1)
                eps.append("%s$%s" % (en, self.site_url + eu))
            if eps:
                groups[nm] = eps
                order.append(nm)

        # 兜底：整页扫 data-origin 分组（豆花式结构），同样产出字符串列表
        if not groups:
            for m in _RE_EPISODE_A.finditer(ph):
                href, attrs, inner = m.group(1), m.group(2), m.group(3)
                mo = _RE_DATA_ORIGIN.search(attrs)
                if not mo or not mo.group(1):
                    continue
                origin = mo.group(1)
                href = href.replace("&amp;", "&")
                if href.startswith("/"):
                    href = self.site_url + href
                ep_name = ""
                mt = _RE_DATA_TITLE.search(attrs)
                if mt:
                    ep_name = self._clean(mt.group(1))
                if not ep_name:
                    mt = _RE_BTN_TITLE.search(inner)
                    if mt:
                        ep_name = self._clean(mt.group(1))
                if not ep_name:
                    ep_name = "第%d集" % (len(groups.get(origin, [])) + 1)
                if origin not in groups:
                    groups[origin] = []
                    order.append(origin)
                groups[origin].append("%s$%s" % (ep_name, href))

        # 线路排序：蓝光优先
        if order:
            order.sort(key=lambda x: (0 if ("蓝光" in x and "高清" in x)
                                      else (1 if "蓝光3" in x else 2)))
        return groups, order

    # ═══════════════ 搜索 ═══════════════
    def searchContent(self, key, quick=False, pg="1"):
        result = {"list": [], "page": 1}
        kw = (key or "").strip()
        if not kw:
            return result
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1

        # 主线：API 搜索（需匿名会话）
        params = {"channelId": "", "k": kw, "next": ""}
        if page > 1:
            params["next"] = "page=%d" % page
        d = self._api("/vod/search/query", params)
        if not d:
            self._anon_login()
            d = self._api("/vod/search/query", params)

        if d:
            for it in (d.get("items") or []):
                v = self._vod(it)
                if v:
                    # 搜索结果标题带 <font> 高亮标签，清掉
                    v["vod_name"] = re.sub(r"<[^>]+>", "", v["vod_name"]).strip()
                    result["list"].append(v)
            result["page"] = page
            return result

        # 备用：网页搜索（该站搜索需要首页下发的 token 参数 t）
        self.log("搜索走网页线")
        tok = self._search_token()
        url = "%s/search?k=%s" % (self.site_url, urllib.parse.quote(kw, safe=""))
        if tok:
            url += "&t=" + urllib.parse.quote(tok, safe="")
        if page > 1:
            url += "&page=%d" % page
        html = self._page(url, timeout=15)
        result["list"] = self._parse_web_items(html, search=True)
        result["page"] = page
        return result

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ═══════════════ 播放 ═══════════════
    def playerContent(self, flag, id, vipFlags=None):
        result = {"parse": 0, "url": "", "header": {"User-Agent": _API_UA}}
        sid = str(id)
        try:
            # 线路 1：API token（vodId|siteId|epId）
            if sid.count("|") >= 2 and not sid.startswith("http"):
                return self._play_api(sid) or result

            # 线路 2：网页 play 页 URL
            if sid.startswith("http") or sid.startswith("/"):
                return self._play_web(sid) or result
        except Exception as e:
            self.log("playerContent ERR: %s" % e)
        return result

    def _play_api(self, sid):
        result = {"parse": 0, "url": "", "header": {"User-Agent": _API_UA}}
        parts = sid.split("|")
        if len(parts) < 3:
            self.log("id 格式不对 -> %s" % sid[:80])
            return None
        vod_id, site_id, ep_id = parts[0], parts[1], parts[2]

        # 重新取详情，拿新鲜签名（sign/timestamp 有时效）
        j = self._api("/v2/vod/detail.capi", {"vodId": vod_id})
        for src in ((j or {}).get("playSources") or []):
            if str(src.get("siteId")) != str(site_id):
                continue
            for ep in (src.get("list") or []):
                if str(ep.get("id")) != str(ep_id):
                    continue
                pus = ep.get("playUrls") or []
                if not pus:
                    continue
                raw = pus[0].get("url") or ""
                if not raw:
                    continue
                # 解析 302 调度，把最终节点地址交给播放器
                final = self._resolve_redirect(raw)
                self.log("play %s -> %s" % (vod_id, final.split("/")[2]))
                wrapped = self._wrap_proxy(final, "type=m3u8")
                if wrapped:
                    # 走 py 代理时清空 header：宿主见到 header 会再套一层
                    # /proxy/m3u8?url=<py代理>&headers=...，形成双重代理。
                    result["url"] = wrapped
                    result["header"] = {}
                else:
                    result["url"] = final
                return result
        self.log("未匹配到剧集 %s" % sid[:80])
        return None

    def _play_web(self, sid):
        """网页 play 页：playSource 提取 + box master 拆子流 + 直链兜底。"""
        play_page = sid if sid.startswith("http") else self._fix_url(sid)
        now = int(time.time())
        hit = self._play_cache.get(play_page)
        if hit and now - hit[0] < 600:
            return hit[1]

        html = self._page(play_page)
        api_url = self._extract_api_m3u8(html) if html else ""
        self.log("play page: %s" % play_page[-60:])
        self.log("  api_url: %s" % (api_url[:160] if api_url else "EMPTY"))

        res = None
        if api_url:
            # 情况 A：直接是 m3u8 直链（短剧常见）
            if api_url.startswith("http") and ".m3u8" in api_url.lower():
                res = {
                    "parse": 0, "playUrl": "", "url": api_url,
                    "header": {"User-Agent": WEB_UA,
                               "Referer": self.site_url + "/"},
                }
                self.log("  => 直链 m3u8")
            else:
                # 情况 B：/api/m3u8?... 需要 302 转换
                if api_url.startswith("/"):
                    api_url = self.site_url + api_url
                real = self._resolve_to_real_m3u8(api_url, referer=play_page)
                if real:
                    res = {
                        "parse": 0, "playUrl": "", "url": real,
                        "header": {"User-Agent": WEB_UA,
                                   "Referer": BOX_HOST + "/"},
                    }
                    self.log("  => 拆出子 m3u8")

        if not res:
            # 兜底：直接找 m3u8；若是 master 播放列表则继续拆子流
            m = _RE_M3U8_ANY.search(html or "")
            if m:
                direct = m.group(1).replace("\\/", "/")
                res = {
                    "parse": 0, "playUrl": "",
                    "url": self._unwrap_master(direct) or direct,
                    "header": {"User-Agent": WEB_UA,
                               "Referer": self.site_url + "/"},
                }
            else:
                res = {"parse": 1, "playUrl": "", "url": play_page,
                       "header": {"User-Agent": WEB_UA,
                                  "Referer": self.site_url + "/"}}

        self._play_cache[play_page] = (now, res)
        return res

    def _unwrap_master(self, url):
        """若 url 是 master 播放列表（内部还有子流），返回第一条子流地址。

        拿不到或不是 master 时原样返回，不改变原有行为。
        """
        try:
            r = self.fetch(url, headers={
                "User-Agent": WEB_UA,
                "Referer": self.site_url + "/",
                "Accept": "*/*",
            }, timeout=20)
            text = r.text if hasattr(r, "text") else ""
        except Exception:
            return url
        if "#EXT-X-STREAM-INF" not in (text or ""):
            return url
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines):
                sub = lines[i + 1].strip()
                full = urljoin(url, sub) if not sub.startswith("http") else sub
                self.log("  master 拆出子流: %s" % full[:120])
                return full
        return url

    def _extract_api_m3u8(self, html):
        if not html:
            return ""
        m = _RE_PLAYER_AA.search(html)
        if not m:
            m2 = re.search(r'(/api/m3u8\?[^"\'\\\s]+)', html)
            if m2:
                return m2.group(1).replace("&amp;", "&")
            return ""
        raw = m.group(1)
        raw = (raw.replace("\\\\u0026", "&").replace("\\u0026", "&")
                  .replace("\\\\u0022", '"').replace("\\u0022", '"')
                  .replace("\\/", "/"))
        try:
            aa = json.loads(raw)
            return aa.get("url", "")
        except Exception:
            m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            return m2.group(1) if m2 else ""

    def _resolve_to_real_m3u8(self, api_url, referer=None):
        """api/m3u8 的 302 -> box master -> 取第一条子流。"""
        hdrs = {
            "User-Agent": WEB_UA,
            "Referer": referer or (self.site_url + "/"),
            "Accept": "text/html,application/json,*/*",
        }
        try:
            try:
                rsp = self.fetch(api_url, headers=hdrs, timeout=15,
                                 allow_redirects=False)
            except TypeError:
                rsp = self.fetch(api_url, headers=hdrs, timeout=15)
        except Exception as e:
            self.log("resolve#1 fail: %s" % e)
            return ""

        loc = ""
        if hasattr(rsp, "headers"):
            loc = rsp.headers.get("Location", "") or rsp.headers.get("location", "")

        if not loc:
            text = rsp.text if hasattr(rsp, "text") else ""
            if "#EXTM3U" in (text or ""):
                self.log("api 直接返回 m3u8")
                return api_url
            return ""

        if loc.startswith("//"):
            loc = "https:" + loc
        loc = loc.replace("&amp;", "&")
        self.log("  box master: %s" % loc[:150])

        try:
            rsp2 = self.fetch(loc, headers={
                "User-Agent": WEB_UA, "Referer": api_url, "Accept": "*/*",
            }, timeout=15)
            text2 = rsp2.text if hasattr(rsp2, "text") else ""
        except Exception as e:
            self.log("resolve#2 fail: %s" % e)
            return loc

        if "#EXTM3U" not in (text2 or ""):
            self.log("  master 无 m3u8 头")
            return loc

        lines = [ln.strip() for ln in text2.split("\n") if ln.strip()]
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines):
                sub = lines[i + 1].strip()
                if sub.startswith("http"):
                    full = sub
                elif sub.startswith("/"):
                    full = BOX_HOST + sub
                else:
                    full = BOX_HOST + "/" + sub
                self.log("  子 m3u8: %s" % full[:160])
                return full

        self.log("  无子 m3u8, 返回 master")
        return loc

    # ═══════════════ 302 调度探测 ═══════════════
    def _resolve_redirect(self, url, depth=0):
        """跟随 CDN 的 302 调度，返回最终节点 URL。

        调度前节点对 m3u8/ts 的请求会 302 到同参数的另一节点；
        分片必须落在最终节点上，否则返回 "OK\\n"。
        """
        if not url or depth > 4:
            return url
        try:
            r = self.sess.get(url, headers={"User-Agent": _API_UA,
                                            "Range": "bytes=0-0"},
                              timeout=10, verify=False, allow_redirects=False)
            loc = r.headers.get("Location")
            if loc:
                self.log("302: %s -> %s" % (url.split("/")[2], loc.split("/")[2]))
                return self._resolve_redirect(loc, depth + 1)
        except Exception as e:
            self.log("302 probe fail: %s" % e)
        return url

    # ═══════════════ 代理（m3u8 改写） ═══════════════
    def _wrap_proxy(self, url, extra=""):
        if not url:
            return url
        getter = getattr(self, "getProxyUrl", None)
        if not callable(getter):
            return url
        try:
            base = getter() or ""
        except Exception:
            return url
        if not base:
            return url
        b64 = base64.b64encode(url.encode("utf-8")).decode("ascii")
        if base.endswith("&") or base.endswith("?"):
            sep = ""
        elif "?" in base:
            sep = "&"
        else:
            sep = "?"
        out = base + sep + "url=" + quote(b64)
        if extra:
            out += "&" + extra.lstrip("&")
        return out

    def _decode_proxy_param(self, param):
        if not param:
            return ""
        if isinstance(param, dict):
            s = param.get("url") or param.get("Url") or ""
        else:
            s = str(param)
        s = str(s).strip()
        if "url=" in s[:24]:
            s = s.split("url=", 1)[1].split("&", 1)[0]
        try:
            s = unquote(s)          # 必须先 unquote 再 b64decode
        except Exception:
            pass
        if s.startswith("http"):
            return s
        for pad in (0, 1, 2, 3):
            try:
                d = base64.b64decode(s + "=" * pad, validate=False).decode("utf-8")
                if d.startswith("http"):
                    return d
            except Exception:
                pass
        return ""

    def _rewrite_m3u8(self, body, base_url):
        """改写 m3u8 内所有相对路径为代理 URL。

        base_url 必须是已跟随 302 之后的地址（r.url），否则分片会落在
        调度前的节点上，返回 3 字节 "OK\\n"。
        """
        out = []
        for line in body.splitlines():
            raw = line.rstrip("\r")
            s = raw.strip()
            if not s:
                out.append(raw)
                continue
            if s.startswith("#"):
                if 'URI="' in s:
                    def _rep(m):
                        ku = urljoin(base_url, m.group(1))
                        return 'URI="%s"' % (self._wrap_proxy(ku, "type=media") or ku)
                    s = re.sub(r'URI="([^"]+)"', _rep, s)
                out.append(s)
                continue
            u = s
            if u.startswith("//"):
                u = "https:" + u
            elif not u.lower().startswith("http"):
                u = urljoin(base_url, u)
            out.append(self._wrap_proxy(u, "type=media") or u)
        return "\n".join(out)

    def localProxy(self, param):
        typ = ""
        if isinstance(param, dict):
            typ = str(param.get("type") or "").lower()
        url = self._decode_proxy_param(param)
        if not url:
            return [500, "text/plain", "bad param", ""]
        hdr = {"User-Agent": _API_UA, "Accept": "*/*"}
        try:
            low = url.lower().split("?", 1)[0]
            r = self.sess.get(url, headers=hdr, timeout=self.timeout, verify=False,
                              allow_redirects=True)   # 跟随 302 调度
            if r.status_code not in (200, 206):
                return [r.status_code, "text/plain", "upstream fail", ""]
            if typ == "m3u8" or low.endswith(".m3u8"):
                body = r.content.decode("utf-8", "ignore")
                if "#EXTM3U" in body:
                    body = self._rewrite_m3u8(body, r.url or url)
                return [200, "application/vnd.apple.mpegurl", body, ""]
            if low.endswith(".key"):
                return [200, "application/octet-stream", r.content, ""]
            return [200, "video/MP2T", r.content, ""]
        except Exception as e:
            return [500, "text/plain", "proxy error: %s" % e, ""]

    # ═══════════════ 网页线：抓取与解析 ═══════════════
    def _warm_up(self):
        if self._warmed:
            return
        try:
            self._page(self.site_url + "/?sion_id=" + self.sion_id, timeout=12)
            self._warmed = True
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _solve_pow(self, html):
        """破解 SHA1 PoW 挑战，返回 attack_key。"""
        m1 = _RE_POW_HASH.search(html or "")
        m2 = _RE_POW_TARGET.search(html or "")
        if not m1 or not m2:
            self.log("PoW: 未找到 hash/target")
            return None

        hash_prefix = m1.group(1)
        target = m2.group(1)
        self.log("PoW: hash=%s target=%s" % (hash_prefix[:16], target[:16]))

        start = time.time()
        prefix_b = hash_prefix.encode()
        for i in range(10000000):
            if hashlib.sha1(prefix_b + str(i).encode()).hexdigest() == target:
                self.log("PoW 破解成功: i=%d 耗时=%.2fs" % (i, time.time() - start))
                return i
            if (i + 1) % 1000000 == 0:
                cost = time.time() - start
                self.log("PoW 进度: %d 万, %.1fs" % ((i + 1) // 10000, cost))
                if cost > 60:
                    self.log("PoW 超时 (>60s)")
                    return None
        self.log("PoW 未在范围内破解")
        return None

    def _page(self, url, timeout=20, headers=None):
        """网页抓取，自动过 PoW 挑战。失败返回空串。"""
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            else:
                text = str(rsp)

            if ("正在检测" in text) or ("sha1(hash" in text and "attack_key" in text):
                self.log("遇到 PoW 挑战, 开始破解...")
                attack_key = self._solve_pow(text)
                if attack_key is None:
                    return text
                sep = "&" if "?" in url else "?"
                new_url = url + sep + "attack_key=" + str(attack_key)
                rsp2 = self.fetch(new_url, headers=h, timeout=timeout)
                text2 = rsp2.text if hasattr(rsp2, "text") else ""
                if "正在检测" in text2 and "sha1(hash" in text2:
                    self.log("再次遇到挑战, 再破一次...")
                    ak2 = self._solve_pow(text2)
                    if ak2 is not None:
                        sep2 = "&" if "?" in new_url else "?"
                        rsp3 = self.fetch(new_url + sep2 + "attack_key=" + str(ak2),
                                          headers=h, timeout=timeout)
                        text2 = rsp3.text if hasattr(rsp3, "text") else str(rsp3)
                return text2
            return text
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url[-60:], e))
            return ""

    def _web_pic(self, p):
        if not p or "logo_placeholder" in p:
            return ""
        return p if p.startswith("http") else WEB_PIC_CDN + p

    def _parse_web_items(self, html, search=False):
        """网页卡片解析。search=True 时走 search-result-item 结构。"""
        out, seen = [], set()
        if not html:
            return out

        if search:
            for m in _RE_SEARCH_ITEM.finditer(html):
                vid, inner = m.group(2), m.group(3)
                if vid in seen:
                    continue
                title = ""
                for attr in ("title", "alt"):
                    tm = re.search(r'%s="([^"]+)"' % attr, inner)
                    if tm:
                        c = self._clean(tm.group(1))
                        if c and not self._is_wm(c):
                            title = c
                            break
                if not title:
                    for t in _RE_SEARCH_TITLE.findall(inner):
                        c = self._clean(t)
                        if c and not self._is_wm(c):
                            title = c
                            break
                pic = ""
                for im in _RE_IMG_ORIGIN.findall(inner):
                    pic = self._web_pic(im)
                    if pic:
                        break
                fb = _RE_SEARCH_FOOT.search(inner)
                if title:
                    seen.add(vid)
                    out.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic or self.default_pic,
                        "vod_remarks": self._clean(fb.group(1)) if fb else "",
                    })
            return out

        # 普通卡片（v-item）
        for m in _RE_VITEM.finditer(html):
            vid, inner = m.group(2), m.group(3)
            if vid in seen:
                continue
            title = ""
            for t in _RE_VITEM_TITLE.findall(inner):
                c = self._clean(t)
                if c and not self._is_wm(c):
                    title = c
                    break
            pic = ""
            for im in _RE_IMG_ORIGIN.findall(inner):
                pic = self._web_pic(im)
                if pic:
                    break
            rb = _RE_VITEM_BOTTOM.search(inner)
            if title and pic:
                seen.add(vid)
                out.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": self._clean(rb.group(1)) if rb else "",
                })

        # 备用：豆花式卡片（/movie/xxx.html）
        if not out:
            for href, alt, pic in _RE_CARD.findall(html):
                href = href.replace("&amp;", "&")
                if href in seen:
                    continue
                seen.add(href)
                out.append({
                    "vod_id": href,
                    "vod_name": self._clean(alt)[:100],
                    "vod_pic": self._web_pic(pic) or self.default_pic,
                    "vod_remarks": "",
                })
        return out

    def _search_token(self):
        """网页搜索令牌：从首页 <input name="t" value="..."> 拿，缓存 5 分钟。"""
        now = time.time()
        if self._token and now - self._token_t < 300:
            return self._token
        html = self._page(self.site_url + "/", timeout=12)
        m = re.search(r'name="t"[^>]*value="([^"]+)"', html or "")
        self._token = m.group(1) if m else ""
        self._token_t = now
        return self._token

    def _page_count(self, html):
        if not html:
            return 1
        pages = re.findall(r'page=(\d+)', html)
        if pages:
            try:
                return max(int(p) for p in pages) + 1
            except Exception:
                pass
        return 9999

    # ═══════════════ 其它 ═══════════════
    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4|flv)(\?|$)", url or "", re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self.sess.close()
        except Exception:
            pass

    def close(self):
        self.destroy()


# ══════════════════════════ 自测 ══════════════════════════
if __name__ == "__main__":
    import sys as _sys
    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    _sp = Spider()
    _sp.init("")
    print("=" * 66)
    print("api_ok   :", _sp._api_ok)
    print("host     :", _sp.host)
    print("host_logic:", _sp.host_logic)
    print("图片组    :", {k: v[:1] for k, v in list(_sp.img_groups.items())[:4]})
    print("频道数    :", len(_sp.vod_tabs))

    print("\n[1] homeContent")
    _hc = _sp.homeContent(True)
    print("    分类:", [c["type_name"] for c in _hc["class"]][:12])
    print("    过滤器:", len(_hc.get("filters") or {}), "个频道")

    print("\n[2] homeVideoContent")
    _hv = _sp.homeVideoContent()["list"]
    print("    条数:", len(_hv))
    for _v in _hv[:4]:
        print("      %-8s %-24s %s" % (_v["vod_id"], _v["vod_name"][:22],
                                        _v.get("vod_remarks", "")[:18]))

    print("\n[3] categoryContent ch:1")
    _cc = _sp.categoryContent("ch:1", 1, False, {})
    print("    条数=%d pagecount=%d" % (len(_cc["list"]), _cc["pagecount"]))
    for _v in _cc["list"][:3]:
        print("      %-8s %s" % (_v["vod_id"], _v["vod_name"][:24]))

    print("\n[3b] 第2页")
    _cc2 = _sp.categoryContent("ch:1", 2, False, {})
    print("    条数=%d 首条=%s" % (len(_cc2["list"]),
                                   _cc2["list"][0]["vod_name"] if _cc2["list"] else "-"))

    if not _hv:
        raise SystemExit(0)

    _vid = _hv[0]["vod_id"]
    for _v in _hv:
        if len(_v["vod_id"]) > 4:
            _vid = _v["vod_id"]
            break

    print("\n[4] detailContent vodId=%s" % _vid)
    _v = (_sp.detailContent([_vid]).get("list") or [{}])[0]
    print("    剧名: %s  年份: %s" % (_v.get("vod_name"), _v.get("vod_year")))
    print("    简介前缀: %s" % (("✓" if (_v.get("vod_content") or "").startswith(INTRO_PREFIX)
                                else "✗") + " " + (_v.get("vod_content") or "")[:30]))
    _froms = (_v.get("vod_play_from") or "").split("$$$")
    print("    线路数: %d  前3: %s" % (len(_froms), _froms[:3]))
    _pu = _v.get("vod_play_url") or ""
    if _pu:
        print("    首集: %s" % _pu.split("$$$")[0].split("#")[0][:110])

    print("\n[5] playerContent")
    if _pu:
        _token = _pu.split("$$$")[0].split("#")[0].split("$")[-1]
        _pc = _sp.playerContent("", _token, None)
        _u = _pc.get("url") or ""
        print("    parse=%s url=%s" % (_pc.get("parse"), _u[:110]))
        _raw = _sp._decode_proxy_param(_u) or _u
        _r = _sp.sess.get(_raw, headers={"User-Agent": _API_UA}, timeout=25,
                          verify=False, allow_redirects=True)
        print("    -> %s %dB %s" % (_r.status_code, len(_r.content),
                                    "✓ #EXTM3U" if b"#EXTM3U" in _r.content else "✗"))
        if b"#EXTM3U" in _r.content:
            _ts = [l.strip() for l in _r.text.splitlines()
                   if l.strip() and not l.strip().startswith("#")]
            print("    分片数: %d  最终节点: %s" % (len(_ts), (_r.url or "").split("/")[2]))
            if _ts:
                _tu = urljoin(_r.url or _raw, _ts[0])
                _rr = _sp.sess.get(_tu, headers={"User-Agent": _API_UA,
                                                 "Range": "bytes=0-8191"},
                                   timeout=25, verify=False, allow_redirects=True)
                print("    首分片: %s %dB %s" % (
                    _rr.status_code, len(_rr.content),
                    "✓ MPEG-TS" if _rr.content[:1] == b"\x47"
                    else "✗ " + repr(_rr.content[:20])))

    print("\n[6] searchContent('兰香')")
    _se = _sp.searchContent("兰香", False, "1")
    print("    命中: %d" % len(_se["list"]))
    for _x in _se["list"][:3]:
        print("      %s" % _x["vod_name"])
