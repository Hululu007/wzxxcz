# coding=utf-8
"""
番茄酱影视 fanqe.cc | TVBox Python 爬虫
苹果CMS V10 + MacPlayer
策略 (A+B):
  - 列表/详情: 标准 HTML 正则
  - 播放: xiguam3u8 直链 → parse=0
          其他加密线路 → parse=1 交给 TVBox 嗅探
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

# ⚠️ type_id 用数字（TVBox 标准）
CLASSES = [
    {"type_id": 1,  "type_name": "电影"},
    {"type_id": 2,  "type_name": "电视剧"},
    {"type_id": 3,  "type_name": "综艺"},
    {"type_id": 4,  "type_name": "动漫"},
    {"type_id": 46, "type_name": "体育"},
]

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
    ],
    "46": [{"n": "全部", "v": ""}],
}

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)]

# ⚠️ FILTERS 的 key 用字符串
FILTERS = {}
for c in CLASSES:
    tid = str(c["type_id"])
    FILTERS[tid] = [
        {"key": "class", "name": "分类",
         "value": _SUB_CLASS.get(tid, [{"n": "全部", "v": ""}])},
        {"key": "year",  "name": "年份", "value": _YEARS},
    ]


# ===================== 正则 =====================
_RE_CARD = re.compile(
    r'<a[^>]+href="(/index\.php/vod/detail/id/\d+\.html)"[^>]*>'
    r'[\s\S]{0,500}?'
    r'<img[^>]+data-src="([^"]+)"[^>]*alt="([^"]*)"',
    re.S | re.I)

_RE_CARD_ALT = re.compile(
    r'<div class="public-list-box[^"]*"[^>]*>'
    r'[\s\S]{0,800}?'
    r'href="(/index\.php/vod/detail/id/\d+\.html)"'
    r'[\s\S]{0,800}?'
    r'data-src="([^"]+)"',
    re.S | re.I)

_RE_TITLE_H1 = re.compile(
    r'<h1[^>]*class="[^"]*slide-info-title[^"]*"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE_TAG = re.compile(r'<title>([\s\S]*?)</title>', re.I)

_RE_PIC = re.compile(
    r'<img[^>]+class="[^"]*detail-pic[^"]*"[^>]+data-src="([^"]+)"', re.I)
_RE_PIC_ANY = re.compile(
    r'<img[^>]+data-src="(https?://[^"]+\.(?:jpg|png|webp)[^"]*)"', re.I)

_RE_INTRO = re.compile(
    r'<div[^>]+id="height_limit"[^>]*>([\s\S]*?)</div>', re.S | re.I)
_RE_INTRO2 = re.compile(
    r'<div[^>]+class="[^"]*text cor3[^"]*"[^>]*>([\s\S]*?)</div>', re.S | re.I)

_RE_DIRECTOR = re.compile(
    r'<strong[^>]*class="r6"[^>]*>导演：</strong>([\s\S]*?)</div>', re.S | re.I)
_RE_ACTOR = re.compile(
    r'<strong[^>]*class="r6"[^>]*>主演：</strong>([\s\S]*?)</div>', re.S | re.I)
_RE_REMARKS = re.compile(
    r'<span[^>]*class="[^"]*slide-info-remarks[^"]*"[^>]*>([\s\S]*?)</span>',
    re.S | re.I)

_RE_LINE_BTN = re.compile(
    r'<a\s+data-form="([^"]+)"[^>]*class="[^"]*vod-playerUrl[^"]*"[^>]*>'
    r'([\s\S]*?)</a>', re.S | re.I)

_RE_EP_UL = re.compile(
    r'<ul\s+class="[^"]*anthology-list-play[^"]*"[^>]*>([\s\S]*?)</ul>',
    re.S | re.I)
_RE_EP_A = re.compile(
    r'<a[^>]+href="(/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"[^>]*>'
    r'([\s\S]*?)</a>', re.S | re.I)

_RE_PAGECOUNT = re.compile(r'当前(\d+)/(\d+)页')


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
            if hasattr(rsp, "text"):
                return rsp.text or ""
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)
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

    # ⚠️ 用 raw_decode 提取嵌套 JSON
    def _extract_json_var(self, html, var_name):
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
        if not matches:
            matches = _RE_CARD_ALT.findall(html)
            self.log("  兜底匹配: %d 条" % len(matches))

        for href, pic, alt in matches:
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(alt)[:100],
                "vod_pic":     self._fix_url(pic) or DEFAULT_PIC,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = _RE_PAGECOUNT.search(html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        pages = re.findall(r'/page/(\d+)\.html', html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        return 1

    # ⚠️ 加日志
    def homeContent(self, filter=False):
        self.log("homeContent called, classes=%d, filters=%d"
                 % (len(CLASSES), len(FILTERS)))
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        real_tid = str(extend.get("class") or tid)
        year = extend.get("year") or ""

        parts = ["/index.php/vod/show/id/%s" % real_tid]
        if page > 1:
            parts.append("/page/%d" % page)
        if year:
            parts.append("/year/%s" % year)
        url = self.site_url + "".join(parts) + ".html"

        self.log("category: tid=%s real_tid=%s page=%d year=%s"
                 % (tid, real_tid, page, year))
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
        m = _RE_TITLE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_TITLE_TAG.search(html)
            if m:
                name = self._clean(m.group(1).split("-")[0].split("_")[0])
        name = name or vod_id

        pic = DEFAULT_PIC
        m = _RE_PIC.search(html)
        if not m:
            m = _RE_PIC_ANY.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        content = ""
        m = _RE_INTRO.search(html)
        if not m:
            m = _RE_INTRO2.search(html)
        if m:
            content = self._clean(m.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            director = self._clean(m.group(1))
        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            actor = re.sub(r"\s*,\s*", ", ", self._clean(m.group(1)))

        remarks = ""
        m = _RE_REMARKS.search(html)
        if m:
            remarks = self._clean(m.group(1))

        line_btns = _RE_LINE_BTN.findall(html)
        ep_uls = _RE_EP_UL.findall(html)
        self.log("  线路按钮: %d, 剧集ul: %d" % (len(line_btns), len(ep_uls)))

        play_from = []
        play_url = []

        if line_btns and ep_uls and len(line_btns) == len(ep_uls):
            for (data_form, btn_html), ul_html in zip(line_btns, ep_uls):
                eps = _RE_EP_A.findall(ul_html)
                if not eps:
                    continue
                line_name = self._clean(btn_html)
                line_name = re.sub(r"\d+$", "", line_name).strip() or data_form
                play_from.append(line_name)
                play_url.append("#".join(
                    "%s$%s" % (self._clean(ep_name), self._fix_url(href))
                    for href, ep_name in eps))
        else:
            self.log("  线路/剧集数量不匹配, 走兜底分组")
            groups = {}
            for href, ep_html in _RE_EP_A.findall(html):
                m2 = re.search(r'/sid/(\d+)/nid/(\d+)', href)
                if not m2:
                    continue
                sid = m2.group(1)
                ep_name = self._clean(ep_html) or ("第%s集" % m2.group(2))
                groups.setdefault(sid, []).append((ep_name, self._fix_url(href)))
            for sid in sorted(groups.keys()):
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

        # ---- A: player_aaaa（用 raw_decode 解析嵌套 JSON）----
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

        # ---- A: fqPreheat（用 raw_decode 解析嵌套 JSON）----
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

        # ---- B: 兜底交给 TVBox 嗅探 ----
        self.log("  => 无直链, 交给 TVBox 嗅探 (parse=1)")
        res = {
            "parse": 1, "playUrl": "", "url": play_page,
            "header": {
                "User-Agent": UA,
                "Referer": self.site_url + "/",
            },
        }
        self._play_cache[play_page] = (now, res)
        return res

    def localProxy(self, param):
        return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
