# coding=utf-8
"""
滴答影院 www.loldyw.com | TVBox Python 爬虫
严格对照真实源码：
  - 首页/分类：/genre/{id}.html、/genre/{id}-{page}.html
  - 搜索：/lookup/wd/{关键词}.html
  - 详情：/film/{id}f.html
  - 播放：var player_aaaa={...} 取 url
"""
import re
import sys
import json
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
                adapter = _rq.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
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
                print("[loldyw]", *a)
            except Exception:
                pass
    Spider = _BaseSpider

HOST = "https://www.loldyw.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/three/statics/img/load.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 严格按照首页导航栏的真实大类定义
CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "24", "type_name": "短剧"},
]

# 屏蔽复杂的筛选，保证必定出数据
FILTERS = {}

# ================= 3. 正则解析（精准提取） =================
# 列表卡片，兼容 lazyload 和普通 src
_RE_CARD = re.compile(
    r'<a\s+[^>]*class="[^"]*iqy-vodlist__thumb[^"]*"[^>]*'
    r'href="([^"]+)"[^>]*'
    r'title="([^"]*)"[^>]*'
    r'(?:data-original|data-src|src)="([^"]*)"',
    re.S | re.I)

# 详情页
_RE_H1 = re.compile(r'<h1 class="title">([\s\S]*?)</h1>', re.I)
_RE_DETAIL_PIC = re.compile(r'class="iqy-vodlist__thumb[^"]*picture"[^>]*>[\s\S]*?data-original="([^"]+)"', re.I)
_RE_DESC = re.compile(r'<span class="sketch content">([\s\S]*?)</span>', re.S | re.I)
_RE_RATING = re.compile(r'<span class="branch">([\d.]+)</span>', re.I)
_RE_ACTOR = re.compile(r'<p class="data"><span class="text-muted">主演：</span>([\s\S]*?)</p>', re.S)
_RE_DIRECTOR = re.compile(r'<p class="data"><span class="text-muted">导演：</span>([\s\S]*?)</p>', re.S)
_RE_REMARK = re.compile(r'<span class="text-muted">更新：</span><span class="text-red">([^<]+)</span>', re.I)

# 详情剧集
_RE_LINE_TAB = re.compile(r'<li[^>]*><a href="#(playlist\d+)"[^>]*>([^<]+)</a></li>', re.I)
_RE_LINE_BLOCK = re.compile(r'<div id="(playlist\d+)"[\s\S]*?<ul class="iqy-content__list[^"]*"[\s\S]*?</ul>', re.S | re.I)
_RE_EP = re.compile(r'<a class="btn btn-default[^"]*"\s+href="([^"]+)">([^<]+)</a>', re.I)

# 播放器
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.S)


class Spider(Spider):

    def getName(self):
        return "滴答影院"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}

    def _fetch(self, url, timeout=20):
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=timeout)
            return rsp.text if hasattr(rsp, "text") else (rsp.content.decode("utf-8", "ignore") if hasattr(rsp, "content") else str(rsp))
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _fix(self, url):
        if not url: return ""
        url = url.strip()
        if url.startswith("//"): return "https:" + url
        if url.startswith("http"): return url
        if url.startswith("/"): return self.site_url + url
        return urllib.parse.urljoin(self.site_url + "/", url)

    def _clean(self, s):
        if not s: return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ").replace("&amp;", "&")
             .replace("&quot;", '"').replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _parse_list(self, html):
        videos, seen = [], set()
        # 使用严格的正则提取卡片
        for m in _RE_CARD.finditer(html or ""):
            href, name, pic = m.group(1), m.group(2), m.group(3)
            if href in seen: continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(name),
                "vod_pic": self._fix(pic) or self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._parse_list(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1

        # 严格按照分类页真实路径 /genre/{id}.html
        if page <= 1: 
            url = "%s/genre/%s.html" % (self.site_url, tid)
        else: 
            url = "%s/genre/%s-%d.html" % (self.site_url, tid, page)

        self.log("category: %s" % url)
        html = self._fetch(url)

        pagecount = 9999
        m = re.search(r'href="[^"]*-(\d+)\.html">尾页</a>', html)
        if m: pagecount = int(m.group(1))
        else:
            nums = [int(x) for x in re.findall(r'-(\d+)\.html', html)]
            if nums: pagecount = max(nums)

        return {"list": self._parse_list(html), "page": page, "pagecount": pagecount, "limit": 24, "total": pagecount * 24}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        url = "%s/lookup/wd/%s.html" % (self.site_url, kw) if page == 1 else "%s/lookup/wd/%s-%d.html" % (self.site_url, kw, page)
        html = self._fetch(url)
        return {"list": self._parse_list(html), "page": page, "pagecount": 1, "limit": 24, "total": 999}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids: return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix(vod_id)
        html = self._fetch(url)
        if not html: return {"list": []}

        name = ""
        m = _RE_H1.search(html)
        if m: name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m: name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = name or vod_id

        pic = self.default_pic
        m = _RE_DETAIL_PIC.search(html)
        if m: pic = self._fix(m.group(1))

        content = ""
        m = re.search(r'<span class="data" style="display: none;">([\s\S]*?)</span>', html)
        if m: content = self._clean(m.group(1))
        if not content:
            m = _RE_DESC.search(html)
            if m: content = self._clean(m.group(1))
        content = INTRO_PREFIX + ("\n" + content if content else "")

        actor = ""
        m = _RE_ACTOR.search(html)
        if m: actor = self._clean("".join(re.findall(r'>([^<>]+)</a>', m.group(1))))
        director = ""
        m = _RE_DIRECTOR.search(html)
        if m: director = self._clean("".join(re.findall(r'>([^<>]+)</a>', m.group(1))))

        score = ""
        m = _RE_RATING.search(html)
        if m: score = m.group(1)
        remark = ""
        m = _RE_REMARK.search(html)
        if m: remark = self._clean(m.group(1))

        tab_names = {m.group(1): self._clean(m.group(2)) for m in _RE_LINE_TAB.finditer(html)}
        play_from, play_url = [], []
        for m in _RE_LINE_BLOCK.finditer(html):
            pid = m.group(1)
            eps = []
            for em in _RE_EP.finditer(m.group(0)):
                ep_href = em.group(1).replace("&amp;", "&")
                if ep_href.startswith("/"): ep_href = self.site_url + ep_href
                eps.append("%s$%s" % (self._clean(em.group(2)), ep_href))
            if eps:
                play_from.append(tab_names.get(pid, pid))
                play_url.append("#".join(eps))

        if not play_from: return {"list": []}

        return {"list": [{
            "vod_id": vod_id, "vod_name": name, "vod_pic": pic,
            "vod_content": content, "vod_actor": actor, "vod_director": director,
            "vod_score": score, "vod_remarks": remark or ("%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from), "vod_play_url": "$$$".join(play_url)
        }]}

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix(id)
        if play_page in self._play_cache: return self._play_cache[play_page]

        html = self._fetch(play_page)
        m = _RE_PLAYER.search(html or "")
        if not m:
            return {"parse": 1, "playUrl": "", "url": play_page, "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

        try:
            cfg = json.loads(m.group(1))
        except Exception:
            return {"parse": 1, "playUrl": "", "url": play_page, "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

        url = cfg.get("url") or ""
        if url and cfg.get("encrypt") == 0 and url.startswith("http"):
            res = {"parse": 0, "playUrl": "", "url": url, "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
            self._play_cache[play_page] = res
            return res

        return {"parse": 1, "playUrl": "", "url": play_page, "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

    def isVideoFormat(self, url): return ".m3u8" in url or ".mp4" in url
    def manualVideoCheck(self): return False
    def destroy(self): pass
    def close(self): self.destroy()
