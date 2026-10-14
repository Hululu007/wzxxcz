# coding=utf-8
"""
追风电影网 etisp.com | TVBox Python 爬虫
网站结构：
  - 分类: /z/{tid}.html        分页 /z/{tid}-{page}.html
  - 筛选: /search.php?searchtype=5&tid={tid}&area=xx&year=xxxx
  - 卡片: <a class="stui-vodlist__thumb lazyload" href="/f/{id}.html"
            title="name" data-original="pic"> <span class="pic-text">remarks</span>
  - 详情: og: meta 提供 area/class/director/actor/image
          简介: .detail-content
          选集: ul.stui-content__playlist 三组, /play/{vid}-{sid}-{nid}.html
  - 播放: 播放页内联 <script> var now="m3u8直链" </script>
  - 搜索: /search.php?searchword=xx
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
                print("[etisp]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.etisp.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/statics/img/favicon.ico"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ============ 分类 ============
CLASSES = [
    {"type_id": "1",  "type_name": "电视剧"},
    {"type_id": "2",  "type_name": "电影"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
]

_SUB_CLASS = {
    "1":  [("全部", "1"), ("国产剧", "5"), ("香港剧", "6"), ("台湾剧", "7"),
           ("欧美剧", "8"), ("韩国剧", "9"), ("日本剧", "10"),
           ("泰国剧", "11"), ("海外剧", "12"), ("精品短剧", "13")],
    "2":  [("全部", "2")],
    "3":  [("全部", "3")],
    "4":  [("全部", "4")],
}

_AREAS = ["全部", "大陆", "香港", "台湾", "日本", "韩国", "欧美", "泰国", "其他"]
_YEARS = ["全部"] + [str(y) for y in range(2026, 2013, -1)]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "sub", "name": "子类",
         "value": [{"n": n, "v": "" if n == "全部" else v}
                   for n, v in _SUB_CLASS.get(tid, [("全部", tid)])]},
        {"key": "area", "name": "地区",
         "value": [{"n": x, "v": "" if x == "全部" else x} for x in _AREAS]},
        {"key": "year", "name": "年份",
         "value": [{"n": x, "v": "" if x == "全部" else x} for x in _YEARS]},
    ]


# ===================== 正则 =====================
# 卡片: <a class="stui-vodlist__thumb lazyload" href="/f/{id}.html" title="..."
_RE_CARD = re.compile(
    r'<a class="stui-vodlist__thumb lazyload"\s+href="(/f/\d+\.html)"\s+'
    r'title="([^"]*)"\s+data-original="([^"]*)"[\s\S]*?'
    r'<span class="pic-text[^"]*">([^<]*)</span>',
    re.S | re.I)

# 分页: /z/{tid}-{page}.html
_RE_PAGE = re.compile(r'href="/z/\d+-(\d+)\.html"', re.I)

# 详情: og: meta
_RE_OG = re.compile(
    r'<meta property="og:([^"]+)" content="([^"]*)"', re.I)

# 简介
_RE_DESC_FULL = re.compile(
    r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', re.I)
_RE_DESC_SKETCH = re.compile(
    r'<span class="detail-sketch"[^>]*>([\s\S]*?)</span>', re.I)

# 选集三组: <div id="down3-2" ...> ... </div> 下 ul>li>a
_RE_TAB_PANE = re.compile(
    r'<div id="down(\d)-\d"[^>]*>([\s\S]*?)</div>\s*(?=<div id="down|\s*</div>\s*</div>\s*</div>)',
    re.S | re.I)
_RE_EP = re.compile(
    r'<a[^>]*href="(/play/[^"]+\.html)"[^>]*>([^<]*)</a>', re.I)

# 播放页 now
_RE_NOW = re.compile(r'var\s+now\s*=\s*"([^"]+)"', re.I)

# 搜索页面的卡片复用 _RE_CARD


class Spider(Spider):

    def getName(self):
        return "追风电影网"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
        }
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

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

    # ---------- 列表 ----------
    def _parse_cards(self, html):
        videos = []
        seen = set()
        for m in _RE_CARD.finditer(html or ""):
            href, title, pic, remarks = m.groups()
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(title) or href,
                "vod_pic": self._fix_url(pic) or DEFAULT_PIC,
                "vod_remarks": self._clean(remarks),
            })
        return videos

    def _parse_pagecount(self, html):
        nums = [int(x) for x in _RE_PAGE.findall(html or "")]
        return max(nums) if nums else 1

    # ---------- TVBox 接口 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._parse_cards(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}

        sub = extend.get("sub") or ""
        area = extend.get("area") or ""
        year = extend.get("year") or ""
        real_tid = sub or tid

        if not (area or year):
            # 普通分类分页
            url = "%s/z/%s.html" % (self.site_url, real_tid)
            if page > 1:
                url = "%s/z/%s-%d.html" % (self.site_url, real_tid, page)
        else:
            # 筛选走 search.php
            params = {"searchtype": "5", "tid": real_tid}
            if area:
                params["area"] = area
            if year:
                params["year"] = year
            if page > 1:
                params["page"] = page
            url = "%s/search.php?%s" % (
                self.site_url, urllib.parse.urlencode(params))

        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        pagecount = self._parse_pagecount(html) if not (area or year) else page
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        params = {"searchword": key}
        if page > 1:
            params["page"] = page
        url = "%s/search.php?%s" % (
            self.site_url, urllib.parse.urlencode(params))
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        return {"list": videos, "page": page, "pagecount": page,
                "limit": 24, "total": 999}

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

        # 标题
        name = ""
        m = re.search(r'<h1 class="title"[^>]*>([\s\S]*?)</h1>', html, re.I)
        if m:
            name = self._clean(m.group(1))
        if not name:
            mt = re.search(r"<title>(.*?)</title>", html, re.S)
            if mt:
                name = self._clean(mt.group(1).split("_")[0])
        name = name or vod_id

        # og meta
        og = {}
        for k, v in _RE_OG.findall(html):
            og[k.lower()] = v

        # 封面
        pic = self._fix_url(og.get("image", "")) or DEFAULT_PIC

        # 导演 / 主演
        director = self._clean(og.get("video:director", ""))
        actor = self._clean(og.get("video:actor", ""))
        if actor:
            actor = re.sub(r"\s*,\s*", ", ", actor)

        # 年份 / 地区 / 类型
        year = ""
        area = self._clean(og.get("video:area", ""))
        type_name = self._clean(og.get("video:class", ""))
        # 年份: 从 <a href="?year=xxxx"> 抓
        my = re.search(r'year=(\d{4})', html)
        if my:
            year = my.group(1)

        # 简介: 优先 detail-content, 兜底 detail-sketch
        content = ""
        m = _RE_DESC_FULL.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_DESC_SKETCH.search(html)
            if m:
                content = self._clean(m.group(1))
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # 选集: 三组线路
        # tab id 映射: down3-2 -> 腾讯视频(sid=2), down2-2 -> 优酷视频(sid=1), down1-2 -> 奇艺视频(sid=0)
        line_names = {
            "3": "腾讯视频",
            "2": "优酷视频",
            "1": "奇艺视频",
        }
        groups = []
        for line_id, block in _RE_TAB_PANE.findall(html):
            eps = []
            for ep_href, ep_name in _RE_EP.findall(block):
                eps.append((self._clean(ep_name) or "播放",
                            self._fix_url(ep_href)))
            if eps:
                groups.append((line_names.get(line_id, "线路%s" % line_id), eps))

        if not groups:
            return {"list": []}

        # 按 line_id 排序: 3->2->1 (和网站 tab 顺序一致)
        play_from = [g[0] for g in groups]
        play_url = ["#".join("%s$%s" % (n, h) for n, h in g[1]) for g in groups]

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": "",
            "vod_year": year,
            "vod_area": area,
            "vod_remarks": ("%d条线路" % len(groups)) if groups else "",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

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
        play_url = ""
        m = _RE_NOW.search(html)
        if m:
            play_url = m.group(1).replace("\\/", "/").replace("&amp;", "&")

        if play_url:
            self.log("  now: %s" % play_url[:200])
            res = {
                "parse": 0,
                "playUrl": "",
                "url": play_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": play_page,
                },
            }
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        pass

    def close(self):
        self.destroy()
