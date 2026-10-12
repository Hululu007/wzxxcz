# coding=utf-8
"""
不卡影视 bukayingshi.com | TVBox Python 爬虫
网站结构：
  - 分类 /buka/{1-5}.html，翻页 /buka/{type}-{page}.html
  - 筛选 /vodshow/{type}-{area}-{lang}-{class}-{year}-{sort}-{page}.html
  - 搜索 /vodsearch/{kw}----------{page}---.html
  - 详情 /ying/{id}.html，剧集 .episode-item -> /shi/{id}-{sid}-{nid}.html
  - 播放 player_aaaa.url 是 share 页；请求 share 页提取 var main 的 m3u8，
    拼上 share 页 origin，直出给 TVBox
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
                print("[bukayingshi]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.bukayingshi.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/static/images/logo.jpg"

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "5", "type_name": "短剧"},
]

_AREAS = [
    ("全部", ""), ("内地", "内地"), ("韩国", "韩国"), ("香港", "香港"),
    ("台湾", "台湾"), ("日本", "日本"), ("美国", "美国"), ("泰国", "泰国"),
    ("英国", "英国"), ("新加坡", "新加坡"), ("其他", "其他"),
]
_LANGS = [
    ("全部", ""), ("国语", "国语"), ("英语", "英语"), ("粤语", "粤语"),
    ("闽南语", "闽南语"), ("韩语", "韩语"), ("日语", "日语"), ("其它", "其它"),
]
_YEARS = [("全部", "")] + [(str(y), str(y)) for y in range(2026, 2003, -1)]
_SORTS = [("最新", "time"), ("热门", "hits"), ("评分", "score")]

_CLASS_MAP = {
    "1": ["全部", "喜剧", "爱情", "动作", "科幻", "恐怖", "剧情", "战争",
          "警匪", "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑",
          "惊悚", "经典", "青春", "文艺", "微电影", "纪录片", "预告片"],
    "2": ["全部", "古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
          "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
    "3": ["全部", "真人秀", "脱口秀", "国产综艺", "喜剧", "晚会", "综艺",
          "音乐", "纪录", "游戏", "生活", "港台综艺", "日韩综艺", "剧情",
          "文化", "相声", "情感", "悬疑", "欧美综艺", "美食", "竞技"],
    "4": ["全部", "动画", "冒险", "喜剧", "奇幻", "剧情", "科幻", "动作",
          "儿童", "悬疑", "都市", "家庭", "国漫", "日常", "爱情", "玄幻",
          "日漫", "音乐", "治愈", "短片", "古风", "犯罪", "武侠", "运动", "校园"],
    "5": ["全部", "AI漫剧", "短剧", "剧情", "爱情", "爽文", "古装", "短片",
          "悬疑", "喜剧", "奇幻", "都市", "玄幻", "犯罪", "家庭", "穿越",
          "惊悚", "武侠", "科幻", "动作", "冒险", "恐怖", "青春", "历史"],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "类型",
         "value": [{"n": x, "v": "" if x == "全部" else x}
                   for x in _CLASS_MAP.get(tid, ["全部"])]},
        {"key": "area", "name": "地区",
         "value": [{"n": n, "v": v} for n, v in _AREAS]},
        {"key": "lang", "name": "语言",
         "value": [{"n": n, "v": v} for n, v in _LANGS]},
        {"key": "year", "name": "年份",
         "value": [{"n": n, "v": v} for n, v in _YEARS]},
        {"key": "sort", "name": "排序",
         "value": [{"n": n, "v": v} for n, v in _SORTS]},
    ]


# ============ 正则 ============
_RE_VIDEO_ITEM = re.compile(
    r'<a\s+href="(/ying/\d+\.html)"[^>]*class="[^"]*video-item[^"]*"[^>]*>'
    r'[\s\S]*?<img[^>]*?src="([^"]*)"[^>]*?alt="([^"]*)"',
    re.S | re.I)

_RE_SEARCH_ITEM = re.compile(
    r'<a[^>]*href="(/ying/\d+\.html)"[^>]*class="search_result_list_item"[^>]*>'
    r'([\s\S]*?)</a>',
    re.S | re.I)
_RE_SEARCH_IMG = re.compile(r'<img[^>]*?src="([^"]*)"', re.I)
_RE_SEARCH_TITLE = re.compile(
    r'search_result_list_item_content_title"[^>]*>([^<]*)<', re.I)
_RE_SEARCH_TAG = re.compile(
    r'search_result_list_item_content_tag"[^>]*>([^<]*)<', re.I)

_RE_H1 = re.compile(
    r'<h1[^>]*class="[^"]*font-bold text-2xl[^"]*"[^>]*>([^<]*)</h1>', re.I)
_RE_DETAIL_PIC = re.compile(r'<img\s+alt="[^"]*"\s+src="([^"]+)"', re.I)
_RE_A_TAG = re.compile(r'<a[^>]*>([^<]*)</a>', re.I)

_RE_ROW = re.compile(
    r'video_appraise_title font-bold"[^>]*>([^<]*)</span>\s*'
    r'<div class="video_appraise_list"[^>]*>([\s\S]*?)</div>',
    re.S | re.I)

_RE_SHORT_DESC = re.compile(
    r'<span class="video-description-short">([\s\S]*?)</span>', re.I)

_RE_EPISODE = re.compile(
    r'<a[^>]*href="(/shi/\d+-\d+-\d+\.html)"[^>]*class="episode-item"'
    r'(?:[^>]*data-episode-name="([^"]*)")?[^>]*>',
    re.S | re.I)

_RE_LINE_ITEM = re.compile(
    r'<div[^>]*class="[^"]*detail_line_ite[^"]*"[^>]*data-source="(\d+)"'
    r'[^>]*>[\s\S]*?<div[^>]*>([^<]*)</div>',
    re.S | re.I)

_RE_PLAYER_AAAA = re.compile(
    r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)

# share 页里 m3u8 变量：var main = "/xxx/index.m3u8?sign=xxx"
_RE_SHARE_MAIN = re.compile(
    r'var\s+main\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']', re.I)
_RE_M3U8_ANY = re.compile(
    r'["\']([^"\']+\.m3u8[^"\']*)["\']', re.I)

_RE_TAIL_PAGE = re.compile(
    r'href="/buka/\d+-(\d+)\.html"[^>]*>\s*<button[^>]*>\s*<span[^>]*>尾页', re.I)
_RE_PAGE_INFO = re.compile(r'<span>(\d+)/(\d+)</span>')


class Spider(Spider):

    def getName(self):
        return "不卡影视"

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

    # ---------- 基础 ----------
    def _fetch(self, url, timeout=20, headers=None):
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

    # ---------- 列表解析 ----------
    def _parse_video_items(self, html):
        out = []
        seen = set()
        for m in _RE_VIDEO_ITEM.finditer(html):
            href, pic, alt = m.group(1), m.group(2), m.group(3)
            if href in seen:
                continue
            seen.add(href)
            out.append({
                "vod_id": href,
                "vod_name": self._clean(alt)[:120],
                "vod_pic": self._fix_url(pic) or DEFAULT_PIC,
                "vod_remarks": "",
            })
        return out

    def _parse_search_items(self, html):
        out = []
        seen = set()
        for m in _RE_SEARCH_ITEM.finditer(html):
            href = m.group(1)
            block = m.group(2)
            if href in seen:
                continue
            seen.add(href)

            mi = _RE_SEARCH_IMG.search(block)
            pic = self._fix_url(mi.group(1)) if mi else DEFAULT_PIC

            mt = _RE_SEARCH_TITLE.search(block)
            name = self._clean(mt.group(1)) if mt else ""

            mtg = _RE_SEARCH_TAG.search(block)
            remarks = self._clean(mtg.group(1)) if mtg else ""

            out.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": pic or DEFAULT_PIC,
                "vod_remarks": remarks,
            })
        return out

    def _page_count(self, html):
        m = _RE_TAIL_PAGE.search(html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        m = _RE_PAGE_INFO.search(html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        return 1

    # ---------- TVBox 接口 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._parse_video_items(html)}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1

        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        def _v(k):
            v = extend.get(k)
            if v in ("", None, "全部"):
                return ""
            return v

        area = _v("area")
        lang = _v("lang")
        cls = _v("class")
        year = _v("year")
        sort = _v("sort") or "time"

        if area or lang or cls or year or (extend.get("sort") not in ("", None)):
            seg = [
                tid,
                urllib.parse.quote(area) if area else "",
                urllib.parse.quote(lang) if lang else "",
                urllib.parse.quote(cls) if cls else "",
                year or "",
                sort or "time",
            ]
            path = "-".join(seg)
            if page > 1:
                url = "%s/vodshow/%s-%d.html" % (self.site_url, path, page)
            else:
                url = "%s/vodshow/%s.html" % (self.site_url, path)
        else:
            if page > 1:
                url = "%s/buka/%s-%d.html" % (self.site_url, tid, page)
            else:
                url = "%s/buka/%s.html" % (self.site_url, tid)

        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._parse_video_items(html)
        pagecount = self._page_count(html)

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        kw = urllib.parse.quote(key)
        url = "%s/vodsearch/%s----------%d---.html" % (self.site_url, kw, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._parse_search_items(html)
        if not videos:
            videos = self._parse_video_items(html)

        return {
            "list": videos,
            "page": page,
            "pagecount": self._page_count(html),
            "limit": 24,
            "total": 999,
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
        if not html:
            return {"list": []}

        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m2 = re.search(r"<title>《(.*?)》", html)
            if m2:
                name = self._clean(m2.group(1))
        name = name or vod_id

        pic = DEFAULT_PIC
        m = _RE_DETAIL_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        director = actor = area = lang = year = remarks = ""
        for mm in _RE_ROW.finditer(html):
            key = self._clean(mm.group(1))
            val_html = mm.group(2)
            links = _RE_A_TAG.findall(val_html)
            if links:
                val = ", ".join(self._clean(x) for x in links if self._clean(x))
            else:
                val = self._clean(val_html)
            if "导演" in key:
                director = val
            elif "演员" in key or "主演" in key:
                actor = val
            elif "地区" in key:
                area = val
            elif "语言" in key:
                lang = val
            elif "年份" in key:
                year = val
            elif "备注" in key:
                remarks = val

        content = ""
        m = _RE_SHORT_DESC.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(r'name="description"\s+content="([^"]*)"', html)
            if m:
                content = self._clean(m.group(1))

        eps = []
        for m in _RE_EPISODE.finditer(html):
            href = m.group(1)
            ep_name = m.group(2) or ""
            if not ep_name:
                mn = re.search(r'data-episode-name="([^"]*)"', m.group(0))
                ep_name = mn.group(1) if mn else ""
            if not ep_name:
                ep_name = "第%02d集" % (len(eps) + 1)
            eps.append((self._clean(ep_name), self._fix_url(href)))

        if not eps:
            return {"list": []}

        line_name = "buka"
        ml = _RE_LINE_ITEM.search(html)
        if ml:
            line_name = self._clean(ml.group(2)) or "buka"

        play_from = line_name
        play_url = "#".join("%s$%s" % (n, h) for n, h in eps)

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_area": area,
            "vod_lang": lang,
            "vod_year": year,
            "vod_remarks": remarks,
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }]}

    # ---------- share 页 -> 真 m3u8 ----------
    def _resolve_share_url(self, share_url):
        """
        请求 share 页，提取 var main 的 m3u8 地址并补全为绝对 URL。
        验证过：拼出来的 URL 直接可播，无需 Referer。
        """
        try:
            rsp = self.fetch(share_url, headers={
                "User-Agent": UA,
                "Referer": self.site_url + "/",
            }, timeout=15)
        except Exception as e:
            self.log("share fetch fail: %s" % e)
            return ""

        text = ""
        if hasattr(rsp, "text"):
            text = rsp.text or ""
        elif hasattr(rsp, "content"):
            text = rsp.content.decode("utf-8", "ignore")

        if not text:
            return ""

        # 直接就是 m3u8
        if "#EXTM3U" in text:
            return share_url

        # 优先 var main
        m = _RE_SHARE_MAIN.search(text)
        if not m:
            m = _RE_M3U8_ANY.search(text)
        if not m:
            self.log("share 页里没有找到 m3u8")
            return ""

        m3u8 = m.group(1).replace("\\/", "/").replace("&amp;", "&")

        if m3u8.startswith("//"):
            m3u8 = "https:" + m3u8
        elif m3u8.startswith("/"):
            parsed = urllib.parse.urlparse(share_url)
            m3u8 = "%s://%s%s" % (parsed.scheme, parsed.netloc, m3u8)
        elif not m3u8.startswith("http"):
            m3u8 = urllib.parse.urljoin(share_url, m3u8)

        self.log("  resolve m3u8: %s" % m3u8[:200])
        return m3u8

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        share_url = ""
        m = _RE_PLAYER_AAAA.search(html)
        if m:
            raw = m.group(1)
            try:
                data = json.loads(raw)
                share_url = data.get("url", "") or ""
            except Exception:
                m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if m2:
                    share_url = m2.group(1)
        if share_url:
            share_url = share_url.replace("\\/", "/").replace("&amp;", "&")

        if share_url:
            self.log("  share: %s" % share_url[:160])
            real_m3u8 = self._resolve_share_url(share_url)
            if real_m3u8:
                res = {
                    "parse": 0,
                    "playUrl": "",
                    "url": real_m3u8,
                    "header": {
                        "User-Agent": UA,
                        "Referer": share_url,
                    },
                }
                self._play_cache[play_page] = (now, res)
                return res

        # 兜底：交给 TVBox 嗅探
        res = {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }
        self._play_cache[play_page] = (now, res)
        return res

    def localProxy(self, param):
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url", "")
            else:
                for pair in str(param).split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        if k == "url":
                            url = v
            if not url:
                return [200, "image/jpeg", b"", ""]
            url = urllib.parse.unquote(url) if "%" in url else url
            url = self._fix_url(url)
            rsp = self.fetch(url, headers={
                "User-Agent": UA, "Referer": self.site_url + "/"}, timeout=15)
            content = rsp.content
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
