# coding=utf-8
"""
山阳影院 zstjjs.com | TVBox Python 爬虫
网站源码结构编写：
  - 首页/分类/搜索：解析 stui-vodlist__box
  - 详情页：解析 h1.title / p.data / stui-content__playlist
  - 播放页：解析 var player_aaaa={...} 中的 url 字段
  - 筛选：按网站真实 url 规则拼接
"""
import re
import sys
import json
import urllib.parse
import requests

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass

    class _BaseSpider:
        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                self._session = requests.Session()
                self._session.verify = False
                adapter = requests.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def log(self, *a, **kw):
            try:
                print("[zstjjs]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://zstjjs.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/hl045/statics/img/load.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ============ 分类（对应顶部导航） ============
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺片"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "24", "type_name": "短剧"},
]

# ============ 筛选数据（完全按真实网站） ============
_FILTERS = {
    "1": [
        ("class", "按类型", [
            ("全部", ""), ("动作片", "动作片"), ("喜剧片", "喜剧片"),
            ("爱情片", "爱情片"), ("科幻片", "科幻片"), ("剧情片", "剧情片"),
            ("战争片", "战争片"), ("动画片", "动画片"), ("记录片", "记录片"),
            ("恐怖片", "恐怖片"),
        ]),
        ("plot", "按剧情", [
            ("全部", ""), ("喜剧", "喜剧"), ("爱情", "爱情"), ("恐怖", "恐怖"),
            ("动作", "动作"), ("科幻", "科幻"), ("剧情", "剧情"), ("战争", "战争"),
            ("警匪", "警匪"), ("犯罪", "犯罪"), ("动画", "动画"), ("奇幻", "奇幻"),
            ("武侠", "武侠"), ("冒险", "冒险"), ("枪战", "枪战"), ("悬疑", "悬疑"),
            ("惊悚", "惊悚"), ("经典", "经典"), ("青春", "青春"), ("文艺", "文艺"),
            ("微电影", "微电影"), ("古装", "古装"), ("历史", "历史"),
            ("运动", "运动"), ("农村", "农村"), ("儿童", "儿童"),
            ("网络电影", "网络电影"),
        ]),
        ("area", "按地区", [
            ("全部", ""), ("大陆", "大陆"), ("香港", "香港"), ("台湾", "台湾"),
            ("美国", "美国"), ("法国", "法国"), ("英国", "英国"), ("日本", "日本"),
            ("韩国", "韩国"), ("德国", "德国"), ("泰国", "泰国"), ("印度", "印度"),
            ("意大利", "意大利"), ("西班牙", "西班牙"), ("加拿大", "加拿大"),
            ("其他", "其他"),
        ]),
        ("year", "按年份", [("全部", "")] + [(str(y), str(y)) for y in range(2026, 2009, -1)]),
        ("lang", "按语言", [
            ("全部", ""), ("国语", "国语"), ("英语", "英语"), ("粤语", "粤语"),
            ("闽南语", "闽南语"), ("韩语", "韩语"), ("日语", "日语"),
            ("法语", "法语"), ("德语", "德语"), ("其它", "其它"),
        ]),
        ("letter", "按字母", [("全部", "")] + [(c, c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + [("0-9", "0-9")]),
        ("sort", "按排序", [
            ("按时间", "time"), ("按人气", "hits"), ("按评分", "score"),
        ]),
    ],
    "2": [
        ("class", "按类型", [
            ("全部", ""), ("国产剧", "国产剧"), ("香港剧", "香港剧"),
            ("韩国剧", "韩国剧"), ("欧美剧", "欧美剧"), ("台湾剧", "台湾剧"),
            ("日本剧", "日本剧"), ("泰国剧", "泰国剧"), ("海外剧", "海外剧"),
        ]),
        ("plot", "按剧情", [
            ("全部", ""), ("古装", "古装"), ("战争", "战争"), ("青春偶像", "青春偶像"),
            ("喜剧", "喜剧"), ("家庭", "家庭"), ("犯罪", "犯罪"), ("动作", "动作"),
            ("奇幻", "奇幻"), ("剧情", "剧情"), ("历史", "历史"), ("经典", "经典"),
            ("乡村", "乡村"), ("情景", "情景"), ("商战", "商战"), ("网剧", "网剧"),
            ("其他", "其他"),
        ]),
        ("area", "按地区", [
            ("全部", ""), ("内地", "内地"), ("韩国", "韩国"), ("香港", "香港"),
            ("台湾", "台湾"), ("日本", "日本"), ("美国", "美国"), ("泰国", "泰国"),
            ("英国", "英国"), ("新加坡", "新加坡"), ("其他", "其他"),
        ]),
        ("year", "按年份", [("全部", "")] + [(str(y), str(y)) for y in range(2026, 2009, -1)]),
        ("lang", "按语言", [
            ("全部", ""), ("国语", "国语"), ("英语", "英语"), ("粤语", "粤语"),
            ("闽南语", "闽南语"), ("韩语", "韩语"), ("日语", "日语"), ("其它", "其它"),
        ]),
        ("letter", "按字母", [("全部", "")] + [(c, c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + [("0-9", "0-9")]),
        ("sort", "按排序", [
            ("按时间", "time"), ("按人气", "hits"), ("按评分", "score"),
        ]),
    ],
    "3": [
        ("class", "按类型", [
            ("全部", ""), ("大陆综艺", "大陆综艺"), ("日韩综艺", "日韩综艺"),
            ("港台综艺", "港台综艺"), ("欧美综艺", "欧美综艺"),
        ]),
        ("plot", "按剧情", [
            ("全部", ""), ("选秀", "选秀"), ("情感", "情感"), ("访谈", "访谈"),
            ("播报", "播报"), ("旅游", "旅游"), ("音乐", "音乐"), ("美食", "美食"),
            ("纪实", "纪实"), ("曲艺", "曲艺"), ("生活", "生活"),
            ("游戏互动", "游戏互动"), ("财经", "财经"), ("求职", "求职"),
        ]),
        ("area", "按地区", [
            ("全部", ""), ("内地", "内地"), ("港台", "港台"),
            ("日韩", "日韩"), ("欧美", "欧美"),
        ]),
        ("year", "按年份", [("全部", "")] + [(str(y), str(y)) for y in range(2018, 2003, -1)]),
        ("lang", "按语言", [
            ("全部", ""), ("国语", "国语"), ("英语", "英语"), ("粤语", "粤语"),
            ("闽南语", "闽南语"), ("韩语", "韩语"), ("日语", "日语"), ("其它", "其它"),
        ]),
        ("letter", "按字母", [("全部", "")] + [(c, c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + [("0-9", "0-9")]),
        ("sort", "按排序", [
            ("按时间", "time"), ("按人气", "hits"), ("按评分", "score"),
        ]),
    ],
    "4": [
        ("class", "按类型", [
            ("全部", ""), ("国产动漫", "国产动漫"), ("日本动漫", "日本动漫"),
            ("港台动漫", "港台动漫"), ("欧美动漫", "欧美动漫"), ("海外动漫", "海外动漫"),
        ]),
        ("plot", "按剧情", [
            ("全部", ""), ("情感", "情感"), ("科幻", "科幻"), ("热血", "热血"),
            ("推理", "推理"), ("搞笑", "搞笑"), ("冒险", "冒险"), ("萝莉", "萝莉"),
            ("校园", "校园"), ("动作", "动作"), ("机战", "机战"), ("运动", "运动"),
            ("战争", "战争"), ("少年", "少年"), ("少女", "少女"), ("社会", "社会"),
            ("原创", "原创"), ("亲子", "亲子"), ("益智", "益智"),
            ("励志", "励志"), ("其他", "其他"),
        ]),
        ("area", "按地区", [
            ("全部", ""), ("国产", "国产"), ("日本", "日本"),
            ("欧美", "欧美"), ("其他", "其他"),
        ]),
        ("year", "按年份", [("全部", "")] + [(str(y), str(y)) for y in range(2018, 2003, -1)]),
        ("lang", "按语言", [
            ("全部", ""), ("国语", "国语"), ("英语", "英语"), ("粤语", "粤语"),
            ("闽南语", "闽南语"), ("韩语", "韩语"), ("日语", "日语"), ("其它", "其它"),
        ]),
        ("letter", "按字母", [("全部", "")] + [(c, c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + [("0-9", "0-9")]),
        ("sort", "按排序", [
            ("按时间", "time"), ("按人气", "hits"), ("按评分", "score"),
        ]),
    ],
    "24": [
        ("class", "按类型", [
            ("全部", ""), ("短剧大全", "短剧大全"), ("AI漫剧", "AI漫剧"),
        ]),
        ("plot", "按剧情", [("全部", "")]),
        ("area", "按地区", [("全部", "")]),
        ("year", "按年份", [("全部", "")]),
        ("lang", "按语言", [("全部", "")]),
        ("letter", "按字母", [("全部", "")] + [(c, c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + [("0-9", "0-9")]),
        ("sort", "按排序", [
            ("按时间", "time"), ("按人气", "hits"), ("按评分", "score"),
        ]),
    ],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = []
    for key, name, items in _FILTERS.get(tid, []):
        FILTERS[tid].append({
            "key": key, "name": name,
            "value": [{"n": n, "v": v} for n, v in items],
        })


# ===================== 正则 =====================
# 【新增】带 pic-text 角标的卡片（4 个捕获组：href, title, pic, remarks）
_RE_CARD_NEW = re.compile(
    r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*'
    r'href="(/detail/[^"]+)"[^>]*'
    r'title="([^"]*)"[^>]*'
    r'data-original="([^"]*)"[^>]*>'
    r'[\s\S]*?<span[^>]*class="[^"]*pic-text[^"]*"[^>]*>([\s\S]*?)</span>',
    re.S | re.I)

# 原卡片（无 pic-text，3 个捕获组）
_RE_CARD = re.compile(
    r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*'
    r'href="(/detail/[^"]+)"[^>]*'
    r'title="([^"]*)"[^>]*'
    r'data-original="([^"]*)"',
    re.S | re.I)

_RE_CARD2 = re.compile(
    r'<a[^>]*class="[^"]*v-thumb[^"]*"[^>]*'
    r'href="(/detail/[^"]+)"[^>]*'
    r'title="([^"]*)"[^>]*'
    r'(?:data-original|src)="([^"]*)"',
    re.S | re.I)

_RE_H1 = re.compile(r'<h1[^>]*class="title"[^>]*>([\s\S]*?)</h1>', re.I)

_RE_DETAIL_PIC = re.compile(
    r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*picture[^"]*"[^>]*>'
    r'[\s\S]*?<img[^>]*data-original="([^"]+)"', re.I)

_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_OG_IMAGE = re.compile(
    r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_OG_ACTOR = re.compile(
    r'<meta[^>]*property=["\']og:video:actor["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_OG_DIRECTOR = re.compile(
    r'<meta[^>]*property=["\']og:video:director["\'][^>]*content=["\']([^"\']*)["\']', re.I)

_RE_INTRO_DESC = re.compile(
    r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>[\s\S]*?'
    r'<span[^>]*class="[^"]*left[^"]*text-muted[^"]*"[^>]*>简介：</span>\s*'
    r'([\s\S]*?)\s*<a[^>]*href="#desc"',
    re.I)

_RE_DIRECTOR = re.compile(r'<span class="text-muted">导演：</span>([\s\S]*?)</p>', re.I)
_RE_ACTOR = re.compile(r'<span class="text-muted">主演：</span>([\s\S]*?)</p>', re.I)
_RE_YEAR = re.compile(r'<span class="text-muted hidden-xs">年份：</span>([\s\S]*?)</p>', re.I)
_RE_AREA = re.compile(r'<span class="text-muted hidden-xs">地区：</span>([\s\S]*?)</p>', re.I)

# 【新增】更新时间：<p class="data hidden-sm"><span class="text-muted">更新：</span>2026-10-13</p>
_RE_UPDATE = re.compile(r'<span class="text-muted">更新：</span>\s*([\d\-]+)', re.I)

_RE_PLAYLIST_BLOCK = re.compile(
    r'<h3 class="title">\s*<img[^>]*/>\s*([^<]+?)\s*</h3>[\s\S]*?'
    r'<ul class="stui-content__playlist[^"]*">([\s\S]*?)</ul>',
    re.I)
_RE_PLAYLIST_ITEM = re.compile(
    r'<li[^>]*><a[^>]*href="([^"]+)"[^>]*>([^<]+)</a></li>', re.I)

_RE_PLAYER_AAAA = re.compile(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.S)

_RE_PAGE_MAX = re.compile(r'/page/(\d+)\.html', re.I)


class Spider(Spider):

    def getName(self):
        return "山阳影院"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=20, headers=None):
        """直接使用 requests 请求，不依赖 TVBox 基类（基类不保证有 fetch 方法）"""
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = requests.get(url, headers=h, timeout=timeout, verify=False)
            rsp.encoding = 'utf-8'
            return rsp.text or ""
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

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

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ---------- 列表解析（优先带 pic-text 角标） ----------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        # 【改动】优先用带 pic-text 角标的卡片
        matches = _RE_CARD_NEW.findall(html)
        if matches:
            for href, alt, pic, remarks in matches:
                if href in seen:
                    continue
                seen.add(href)
                pic = pic if pic and "load.gif" not in pic else self.default_pic
                videos.append({
                    "vod_id":      href,
                    "vod_name":    self._clean(alt)[:100],
                    "vod_pic":     self._fix_url(pic),
                    "vod_remarks": self._clean(remarks)[:30],
                })
            return videos

        # 兜底：原来的无角标卡片
        matches = _RE_CARD.findall(html)
        if not matches:
            matches = _RE_CARD2.findall(html)

        for href, alt, pic in matches:
            if href in seen:
                continue
            seen.add(href)
            pic = pic if pic and "load.gif" not in pic else self.default_pic
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(alt)[:100],
                "vod_pic":     self._fix_url(pic),
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = _RE_PAGE_MAX.findall(html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        return 9999

    # ---------- TVBox 接口 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        url = self.site_url + "/"
        html = self._fetch(url)
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._extract_videos(html)}

    def _build_category_url(self, tid, pg, extend):
        cls    = extend.get("class", "").strip()
        plot   = extend.get("plot", "").strip()
        area   = extend.get("area", "").strip()
        year   = extend.get("year", "").strip()
        lang   = extend.get("lang", "").strip()
        letter = extend.get("letter", "").strip()
        sort   = extend.get("sort", "").strip() or "time"

        path = "/pack"
        if sort and sort != "time":
            path += "/by/%s" % sort

        if cls:
            sub_id = self._class_to_subid(tid, cls)
            if sub_id:
                path += "/id/%s" % sub_id
            else:
                path += "/id/%s" % tid
        else:
            path += "/id/%s" % tid

        if plot:
            path = path.replace("/id/%s" % (self._class_to_subid(tid, cls) or tid),
                                "/class/%s/id/%s" % (urllib.parse.quote(plot), tid))
            if not cls:
                path = "/pack/class/%s/id/%s" % (urllib.parse.quote(plot), tid)
                if sort and sort != "time":
                    path = "/pack/class/%s/by/%s/id/%s" % (urllib.parse.quote(plot), sort, tid)
        if area:
            path += "/area/%s" % urllib.parse.quote(area)
        if year:
            path += "/year/%s" % year
        if lang:
            path += "/lang/%s" % urllib.parse.quote(lang)
        if letter:
            path += "/letter/%s" % letter
        if pg and int(pg) > 1:
            path += "/page/%d" % int(pg)
        return self.site_url + path + ".html"

    def _class_to_subid(self, tid, cls):
        mapping = {
            "动作片": "6", "喜剧片": "7", "爱情片": "8", "科幻片": "9",
            "剧情片": "10", "战争片": "11", "动画片": "41", "记录片": "12",
            "恐怖片": "39",
            "国产剧": "13", "香港剧": "14", "韩国剧": "15", "欧美剧": "16",
            "台湾剧": "22", "日本剧": "21", "泰国剧": "20", "海外剧": "23",
            "大陆综艺": "25", "日韩综艺": "26", "港台综艺": "27", "欧美综艺": "28",
            "国产动漫": "29", "日本动漫": "30", "港台动漫": "42",
            "欧美动漫": "31", "海外动漫": "43",
            "短剧大全": "40", "AI漫剧": "44",
        }
        return mapping.get(cls, "")

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        url = self._build_category_url(tid, page, extend)
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/find3.html?wd=%s" % (self.site_url, keyword)
        if page > 1:
            url += "&page=%d" % page
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": 1, "limit": 24, "total": len(videos),
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情页 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
            name = re.sub(r"\d+(\.\d+)?$", "", name).strip()
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        pic = self.default_pic
        m = _RE_OG_IMAGE.search(html)
        if m:
            pic = self._fix_url(m.group(1))
        else:
            m = _RE_DETAIL_PIC.search(html)
            if m:
                pic = self._fix_url(m.group(1))

        content = ""
        m = _RE_INTRO_DESC.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
                content = re.sub(r"^《.*?》剧情介绍：", "", content)
                content = re.sub(r"，就来山阳影院.*$", "", content)
                content = re.sub(r"《.*?》剧情观看分集解析.*$", "", content)
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        actor = ""
        m = _RE_OG_ACTOR.search(html)
        if m:
            actor = re.sub(r"\s*,\s*", ", ", m.group(1).strip())
        if not actor:
            m = _RE_ACTOR.search(html)
            if m:
                actor = re.sub(r"\s+", " ", self._clean(m.group(1))).strip()
                actor = re.sub(r"\s*,\s*", ", ", actor)

        director = ""
        m = _RE_OG_DIRECTOR.search(html)
        if m:
            director = re.sub(r"\s*,\s*", ", ", m.group(1).strip())
        if not director:
            m = _RE_DIRECTOR.search(html)
            if m:
                director = re.sub(r"\s+", " ", self._clean(m.group(1))).strip()

        year = ""
        m = _RE_YEAR.search(html)
        if m:
            year = self._clean(m.group(1)).strip("&nbsp; ")
        area = ""
        m = _RE_AREA.search(html)
        if m:
            area = self._clean(m.group(1)).strip("&nbsp; ")

        # 【新增】更新时间
        update_time = ""
        m = _RE_UPDATE.search(html)
        if m:
            update_time = m.group(1).strip()

        play_from = []
        play_url = []
        for block in _RE_PLAYLIST_BLOCK.finditer(html):
            line_name = self._clean(block.group(1))
            ul_html = block.group(2)
            eps = []
            for m2 in _RE_PLAYLIST_ITEM.finditer(ul_html):
                href = m2.group(1).replace("&amp;", "&")
                ep_name = self._clean(m2.group(2))
                if href.startswith("/"):
                    href = self.site_url + href
                eps.append("%s$%s" % (ep_name, href))
            if eps:
                play_from.append(line_name)
                play_url.append("#".join(eps))

        if not play_from:
            self.log("  未找到剧集")
            return {"list": []}

        # 【改动】remarks 拼上更新时间
        remarks = ("%s %s" % (year, area)).strip()
        if update_time:
            remarks = ("%s 更新:%s" % (remarks, update_time)).strip()
        if not remarks:
            remarks = "%d条线路" % len(play_from)

        return {"list": [{
            "vod_id":       vod_id,
            "vod_name":     name,
            "vod_pic":      pic,
            "vod_content":  content,
            "vod_actor":    actor,
            "vod_director": director,
            "vod_year":     year,
            "vod_area":     area,
            "vod_remarks":  remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ---------- 播放 ----------
    def _get_real_m3u8(self, play_page):
        html = self._fetch(play_page)
        if not html:
            return ""
        m = _RE_PLAYER_AAAA.search(html)
        if not m:
            return ""
        try:
            data = json.loads(m.group(1))
            u = data.get("url", "")
            if u:
                return u.replace("\\/", "/")
        except Exception:
            pass
        return ""

    def _find_alternative(self, play_page):
        m = re.match(r'(https?://[^/]+)/frame/(z\d+)/(\d+)/(\d+)\.html', play_page)
        if not m:
            return ""
        host, vid, sid, ep_idx = m.groups()
        detail_url = "%s/detail/%s.html" % (host, vid)
        html = self._fetch(detail_url)
        if not html:
            return ""

        lines = []
        for block in _RE_PLAYLIST_BLOCK.finditer(html):
            line_name = self._clean(block.group(1))
            eps = []
            for m2 in _RE_PLAYLIST_ITEM.finditer(block.group(2)):
                href = m2.group(1).replace("&amp;", "&")
                ep_name = self._clean(m2.group(2))
                if href.startswith("/"):
                    href = host + href
                eps.append((ep_name, href))
            if eps:
                lines.append((line_name, eps))

        cur_ep_name = ""
        for name, eps in lines:
            for en, href in eps:
                if href == play_page:
                    cur_ep_name = en
                    break
            if cur_ep_name:
                break

        if not cur_ep_name:
            try:
                idx = int(ep_idx) - 1
                for name, eps in lines:
                    if 0 <= idx < len(eps):
                        en, href = eps[idx]
                        if href != play_page:
                            return href
            except Exception:
                pass
            return ""

        for name, eps in lines:
            for en, href in eps:
                if en == cur_ep_name and href != play_page:
                    return href
        return ""

    def _build_player_header(self, real_url):
        """按 m3u8 域名判断 Referer：量子资源用站点 Referer，其他第三方 CDN 用空 Referer"""
        host = ""
        try:
            host = (urllib.parse.urlparse(real_url).netloc or "").lower()
        except Exception:
            host = ""
        if "lzcdn" in host:
            ref = self.site_url + "/"
        else:
            ref = ""
        return {"User-Agent": UA, "Referer": ref}

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        real_url = self._get_real_m3u8(play_page)
        if real_url:
            self.log("  => m3u8: %s" % real_url[:160])
            return {
                "parse": 0, "playUrl": "", "url": real_url,
                "header": self._build_player_header(real_url),
            }

        alt = self._find_alternative(play_page)
        if alt:
            real_url = self._get_real_m3u8(alt)
            if real_url:
                self.log("  => 降级到备用线路: %s" % alt)
                return {
                    "parse": 0, "playUrl": "", "url": real_url,
                    "header": self._build_player_header(real_url),
                }

        return {"parse": 1, "playUrl": "", "url": play_page,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

    def localProxy(self, param):
        return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
