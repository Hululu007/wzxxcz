# coding=utf-8
"""
番茄酱影视 fanqe.cc | TVBox Python 爬虫
苹果CMS V10 + MacPlayer
策略 (A+B):
  - 列表/详情: 标准 HTML 正则
  - 播放: 直链 m3u8 → parse=0
          加密线路 → parse=1 交给 TVBox 嗅探
"""
import re
import sys
import json
import time
import urllib.parse

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as _rq
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
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[fanqe]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://fanqe.cc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/static/ds3/img/cover-empty.webp"

INTRO_PREFIX = "🍅番茄酱影视提醒您：请勿相信视频中的广告，谨防上当受骗！"

# ⚠️ type_id 用字符串（TVBox 通用，且和 FILTERS 的 key 一致）
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "46", "type_name": "体育"},
]

# 从网站真实 HTML 抄的，一个不多一个不少
_SUB_CLASS = {
    "1": [
        {"n": "全部",   "v": ""},
        {"n": "动作片", "v": "6"},
        {"n": "喜剧片", "v": "7"},
        {"n": "爱情片", "v": "8"},
        {"n": "科幻片", "v": "9"},
        {"n": "恐怖片", "v": "10"},
        {"n": "剧情片", "v": "11"},
        {"n": "战争片", "v": "12"},
        {"n": "纪录片", "v": "20"},
        {"n": "动画片", "v": "37"},
    ],
    "2": [
        {"n": "全部",   "v": ""},
        {"n": "国产剧", "v": "13"},
        {"n": "香港剧", "v": "14"},
        {"n": "韩国剧", "v": "15"},
        {"n": "欧美剧", "v": "16"},
        {"n": "台湾剧", "v": "21"},
        {"n": "日本剧", "v": "22"},
        {"n": "海外剧", "v": "23"},
        {"n": "泰国剧", "v": "24"},
    ],
    "3": [
        {"n": "全部",     "v": ""},
        {"n": "大陆综艺", "v": "25"},
        {"n": "港台综艺", "v": "26"},
        {"n": "日韩综艺", "v": "27"},
        {"n": "欧美综艺", "v": "28"},
    ],
    "4": [
        {"n": "全部",     "v": ""},
        {"n": "国产动漫", "v": "29"},
        {"n": "日韩动漫", "v": "30"},
        {"n": "欧美动漫", "v": "31"},
        {"n": "港台动漫", "v": "32"},
        {"n": "海外动漫", "v": "33"},
    ],
    "46": [
        {"n": "全部", "v": ""},
        {"n": "足球", "v": "47"},
        {"n": "篮球", "v": "48"},
    ],
}

# 地区：v 是 URL 编码前的原文（拼接时再 quote）
_AREAS = [
    {"n": "全部",   "v": ""},
    {"n": "大陆",   "v": "大陆"},
    {"n": "香港",   "v": "香港"},
    {"n": "台湾",   "v": "台湾"},
    {"n": "美国",   "v": "美国"},
    {"n": "韩国",   "v": "韩国"},
    {"n": "日本",   "v": "日本"},
    {"n": "英国",   "v": "英国"},
    {"n": "法国",   "v": "法国"},
    {"n": "泰国",   "v": "泰国"},
    {"n": "印度",   "v": "印度"},
    {"n": "加拿大", "v": "加拿大"},
    {"n": "西班牙", "v": "西班牙"},
    {"n": "俄罗斯", "v": "俄罗斯"},
    {"n": "德国",   "v": "德国"},
    {"n": "意大利", "v": "意大利"},
    {"n": "其它",   "v": "其它"},
]

# 年份：v 是网站 URL 里的真实值（"XX年前" 是编码后的）
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2019, -1)] + \
         [{"n": "2020年前", "v": "2020%E5%B9%B4%E5%89%8D"},
          {"n": "2010年前", "v": "2010%E5%B9%B4%E5%89%8D"},
          {"n": "2000年前", "v": "2000%E5%B9%B4%E5%89%8D"}]

# FILTERS：key 用 "class"（我内部用），"area"、"year" 都和 URL 参数名一致
FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "类型",
         "value": _SUB_CLASS.get(tid, [{"n": "全部", "v": ""}])},
        {"key": "area",  "name": "地区", "value": _AREAS},
        {"key": "year",  "name": "年份", "value": _YEARS},
    ]


# ===================== 正则（按真实 HTML 写） =====================
# 列表卡片：<a href="/index.php/vod/detail/id/XXXX.html"> ... <img data-src="..." alt="XXX">
_RE_CARD = re.compile(
    r'<a[^>]+href="(/index\.php/vod/detail/id/\d+\.html)"[^>]*>'
    r'[\s\S]{0,800}?'
    r'<img[^>]+data-src="([^"]+)"[^>]*alt="([^"]*)"',
    re.S | re.I)

# 兜底：只找 detail 链接
_RE_DETAIL_HREF = re.compile(
    r'href="(/index\.php/vod/detail/id/\d+\.html)"', re.I)

# 详情页标题
_RE_TITLE_H1 = re.compile(
    r'<h1[^>]*class="[^"]*slide-info-title[^"]*"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE_TAG = re.compile(r'<title>([\s\S]*?)</title>', re.I)

# 详情页封面（class 里含 detail-pic 的 img）
_RE_PIC = re.compile(
    r'<img[^>]+class="[^"]*detail-pic[^"]*"[^>]+data-src="([^"]+)"', re.I)

# 详情页简介：<div id="height_limit" class="text cor3">
_RE_INTRO = re.compile(
    r'<div[^>]+id="height_limit"[^>]*>([\s\S]*?)</div>', re.S | re.I)

# 详情页导演/主演：<strong class="r6">导演：</strong>
_RE_DIRECTOR = re.compile(
    r'<strong[^>]*class="r6"[^>]*>导演：</strong>([\s\S]*?)</div>', re.S | re.I)
_RE_ACTOR = re.compile(
    r'<strong[^>]*class="r6"[^>]*>主演：</strong>([\s\S]*?)</div>', re.S | re.I)

# 详情页备注：<span class="slide-info-remarks">
_RE_REMARKS = re.compile(
    r'<span[^>]*class="[^"]*slide-info-remarks[^"]*"[^>]*>([\s\S]*?)</span>',
    re.S | re.I)

# 详情页线路按钮：<a data-form="xxx" class="vod-playerUrl ...">
_RE_LINE_BTN = re.compile(
    r'<a\s+data-form="([^"]+)"[^>]*class="[^"]*vod-playerUrl[^"]*"[^>]*>'
    r'([\s\S]*?)</a>', re.S | re.I)

# 详情页剧集 ul：<ul class="anthology-list-play ...">
_RE_EP_UL = re.compile(
    r'<ul\s+class="[^"]*anthology-list-play[^"]*"[^>]*>([\s\S]*?)</ul>',
    re.S | re.I)

# 剧集 a：<a class="hide cor4" href="/index.php/vod/play/id/.../sid/.../nid/....html"><span>第01集</span></a>
_RE_EP_A = re.compile(
    r'<a[^>]+href="(/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"[^>]*>'
    r'([\s\S]*?)</a>', re.S | re.I)

# 分页："当前2/15页"
_RE_PAGECOUNT = re.compile(r'当前\s*\d+\s*/\s*(\d+)\s*页')


def _is_direct_m3u8(u):
    if not u or not isinstance(u, str):
        return False
    u = u.strip()
    if not u.startswith("http"):
        return False
    return ".m3u8" in u.lower()


class Spider(Spider):

    def getName(self):
        return "番茄酱影视"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
        }
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=15, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            # TVBox 的 fetch 返回 Response；也有版本直接返回 str
            if hasattr(rsp, "text"):
                return rsp.text or ""
            if hasattr(rsp, "content"):
                try:
                    return rsp.content.decode("utf-8", "ignore")
                except Exception:
                    return ""
            if isinstance(rsp, str):
                return rsp
            return ""
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

    def _extract_json_var(self, html, var_name):
        """从 html 里提取 `var xxx = {...}` 的 JSON（用 raw_decode 处理嵌套）"""
        idx = html.find(var_name)
        if idx < 0:
            return None
        start = html.find("{", idx)
        if start < 0:
            return None
        try:
            obj, _ = json.JSONDecoder().raw_decode(html[start:])
            return obj
        except Exception as e:
            self.log("  %s JSON 解析失败: %s" % (var_name, e))
            return None

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        matches = _RE_CARD.findall(html)
        self.log("  卡片匹配: %d 条" % len(matches))

        for href, pic, alt in matches:
            if href in seen:
                continue
            seen.add(href)
            # alt 形如 "老舅封面图"，去掉末尾"封面图"
            name = self._clean(alt)
            name = re.sub(r'(封面图|海报图|剧照图)$', '', name).strip()
            videos.append({
                "vod_id":      href,
                "vod_name":    name[:100] or href,
                "vod_pic":     self._fix_url(pic) or DEFAULT_PIC,
                "vod_remarks": "",
            })

        # 兜底：只抓 detail 链接
        if not videos:
            hrefs = _RE_DETAIL_HREF.findall(html)
            for href in hrefs:
                if href in seen:
                    continue
                seen.add(href)
                videos.append({
                    "vod_id":      href,
                    "vod_name":    href.split("/id/")[-1].replace(".html", ""),
                    "vod_pic":     DEFAULT_PIC,
                    "vod_remarks": "",
                })
            self.log("  兜底链接: %d 条" % len(videos))

        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = _RE_PAGECOUNT.search(html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        # 兜底：找最大 page
        pages = re.findall(r'/page/(\d+)\.html', html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        return 1

    # -------- 首页分类 tab --------
    def homeContent(self, filter=False):
        self.log("homeContent called, classes=%d, filters=%d"
                 % (len(CLASSES), len(FILTERS)))
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._extract_videos(html)}

    # -------- 分类页 --------
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        # extend 里 "class" 是子分类 id，为空则用主分类 tid
        real_id = str(extend.get("class") or tid)
        area = extend.get("area") or ""
        year = extend.get("year") or ""

        # 按网站真实 URL 顺序拼：
        # /index.php/vod/show/[area/地区/]id/分类/[page/页码/][year/年份/].html
        parts = ["/index.php/vod/show"]
        if area:
            parts.append("/area/%s" % urllib.parse.quote(area, safe=""))
        parts.append("/id/%s" % real_id)
        if page > 1:
            parts.append("/page/%d" % page)
        if year:
            parts.append("/year/%s" % year)
        url = self.site_url + "".join(parts) + ".html"

        self.log("category: tid=%s real_id=%s area=%s year=%s page=%d"
                 % (tid, real_id, area, year, page))
        self.log("  url: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  结果: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    # -------- 搜索 --------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = "%s/index.php/vod/search.html?wd=%s" % (
            self.site_url, urllib.parse.quote(key))
        if page > 1:
            url += "&page=%d" % page
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 24, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # -------- 详情页 --------
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

        # 标题
        name = ""
        m = _RE_TITLE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_TITLE_TAG.search(html)
            if m:
                name = self._clean(m.group(1).split("-")[0].split("_")[0])
        name = name or vod_id

        # 封面
        pic = DEFAULT_PIC
        m = _RE_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        # 简介
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 导演 / 主演
        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            director = self._clean(m.group(1))
        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            actor = re.sub(r"\s*,\s*", ", ", self._clean(m.group(1)))

        # 备注
        remarks = ""
        m = _RE_REMARKS.search(html)
        if m:
            remarks = self._clean(m.group(1))

        # ===== 线路 & 剧集 =====
        line_btns = _RE_LINE_BTN.findall(html)      # [(data_form, btn_html), ...]
        ep_uls = _RE_EP_UL.findall(html)            # [ul_html, ...]
        self.log("  线路按钮: %d, 剧集ul: %d" % (len(line_btns), len(ep_uls)))

        play_from = []
        play_url = []

        # 网站真实：线路按钮顺序 = 剧集 ul 顺序（截图 2 确认）
        if line_btns and ep_uls and len(line_btns) == len(ep_uls):
            for (data_form, btn_html), ul_html in zip(line_btns, ep_uls):
                eps = _RE_EP_A.findall(ul_html)
                if not eps:
                    continue
                line_name = self._clean(btn_html)
                line_name = re.sub(r'\d+$', '', line_name).strip() or data_form
                play_from.append(line_name)
                play_url.append("#".join(
                    "%s$%s" % (self._clean(ep_name) or ("第%d集" % (i + 1)),
                               self._fix_url(href))
                    for i, (href, ep_name) in enumerate(eps)))
        else:
            # 兜底：按 sid 分组
            self.log("  线路/剧集数量不匹配, 按 sid 兜底分组")
            groups = {}
            for href, ep_html in _RE_EP_A.findall(html):
                m2 = re.search(r'/sid/(\d+)/nid/(\d+)', href)
                if not m2:
                    continue
                sid = m2.group(1)
                ep_name = self._clean(ep_html) or ("第%s集" % m2.group(2))
                groups.setdefault(sid, []).append((ep_name, self._fix_url(href)))
            for sid in sorted(groups.keys(), key=lambda x: int(x)):
                play_from.append("线路%s" % sid)
                play_url.append("#".join("%s$%s" % (n, h) for n, h in groups[sid]))

        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id":       vod_id,
            "vod_name":     name,
            "vod_pic":      pic,
            "vod_content":  content,
            "vod_actor":    actor,
            "vod_director": director,
            "vod_remarks":  remarks or ("%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # -------- 播放页 --------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        if not html:
            res = {"parse": 1, "playUrl": "", "url": play_page,
                   "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
            self._play_cache[play_page] = (now, res)
            return res

        # ---- player_aaaa ----
        pa = self._extract_json_var(html, "var player_aaaa")
        if pa:
            url = (pa.get("url") or "").strip()
            from_ = pa.get("from", "")
            encrypt = pa.get("encrypt", 0)
            self.log("  player_aaaa: from=%s encrypt=%s url=%s"
                     % (from_, encrypt, url[:120]))

            if encrypt == 2:
                try:
                    import base64
                    url = base64.b64decode(url).decode("utf-8", "ignore")
                    url = urllib.parse.unquote(url)
                    self.log("    base64 解后: %s" % url[:120])
                except Exception as e:
                    self.log("    base64 解失败: %s" % e)

            if encrypt == 1:
                url = urllib.parse.unquote(url)
                self.log("    unescape 后: %s" % url[:120])

            if _is_direct_m3u8(url):
                self.log("  => 直链 m3u8 (parse=0)")
                res = {
                    "parse": 0, "playUrl": "", "url": url,
                    "header": {
                        "User-Agent": UA,
                        "Referer": self.site_url + "/",
                        "Origin":  self.site_url,
                    },
                }
                self._play_cache[play_page] = (now, res)
                return res

            self.log("  player_aaaa 非直链, 继续找 fqPreheat")

        # ---- fqPreheat ----
        ph = self._extract_json_var(html, "var fqPreheat")
        if ph:
            for ln in ph.get("lines", []):
                u = (ln.get("url") or "").strip()
                if _is_direct_m3u8(u):
                    self.log("  fqPreheat 直链: %s" % u[:120])
                    res = {
                        "parse": 0, "playUrl": "", "url": u,
                        "header": {
                            "User-Agent": UA,
                            "Referer": self.site_url + "/",
                            "Origin":  self.site_url,
                        },
                    }
                    self._play_cache[play_page] = (now, res)
                    return res
            self.log("  fqPreheat 里也无直链")

        # ---- 兜底：交给 TVBox 嗅探 ----
        self.log("  => 无直链, 交给 TVBox 嗅探 (parse=1)")
        res = {
            "parse": 1, "playUrl": "", "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }
        self._play_cache[play_page] = (now, res)
        return res

    def localProxy(self, param):
        return [200, "image/jpeg", b"", b""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
