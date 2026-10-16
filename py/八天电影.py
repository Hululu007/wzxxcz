# coding=utf-8
"""
韩国电影网 shukanbaoxw.com | TVBox Python 爬虫
网站结构（macCMS + ewave 模板 a_0004）
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
                print("[shukanbao]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.shukanbaoxw.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/a_0004/img/load.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 顶级分类（导航栏 /vodtype/{id}.html）
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "20", "type_name": "短剧"},
]

# 子分类（来自各分类筛选页“按分类”）
_SUB_CLASS = {
    "1":  [("全部", "1"), ("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"),
           ("科幻片", "9"), ("恐怖片", "10"), ("剧情片", "11"),
           ("战争片", "12"), ("纪录片", "21"), ("动漫片", "26")],
    "2":  [("全部", "2"), ("国产剧", "13"), ("港剧", "14"), ("台剧", "15"),
           ("日剧", "16"), ("韩剧", "22"), ("泰剧", "23"), ("美剧", "24"),
           ("海外剧", "25")],
    "3":  [("全部", "3"), ("大陆综艺", "27"), ("日韩综艺", "28"),
           ("港台综艺", "29"), ("欧美综艺", "30")],
    "4":  [("全部", "4"), ("国产动漫", "31"), ("日韩动漫", "32"),
           ("港台动漫", "33"), ("欧美动漫", "34"), ("海外动漫", "35")],
    "20": [("全部", "20")],
}

# 年份（所有分类通用）
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

# 地区（每个分类不同，来自各自筛选页“按地区”）
_AREAS = {
    "1": ["全部", "大陆", "香港", "台湾", "美国", "法国", "英国", "日本",
          "韩国", "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
    "2": ["全部", "大陆", "内地", "韩国", "香港", "台湾", "日本", "美国",
          "泰国", "英国", "新加坡", "其他"],
    "3": ["全部", "大陆", "内地", "韩国", "香港", "台湾", "日本", "美国",
          "泰国", "英国", "新加坡", "其他"],
    "4": ["全部", "大陆", "内地", "韩国", "香港", "台湾", "日本", "美国",
          "泰国", "英国", "新加坡", "其他"],
    "20": ["全部", "大陆", "内地", "韩国", "香港", "台湾", "日本", "美国",
           "泰国", "英国", "新加坡", "其他"],
}

# 剧情（每个分类不同，来自各自筛选页“按剧情”）
_GENRES = {
    "1":  ["全部", "喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争",
           "警匪", "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑",
           "惊悚", "经典", "青春", "文艺", "微电影", "古装", "历史", "运动",
           "农村", "儿童", "网络电影"],
    "2":  ["全部", "古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
           "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
    "3":  ["全部", "真人秀", "脱口秀", "喜剧", "晚会", "音乐", "纪录", "游戏",
           "生活", "文化", "相声", "情感", "悬疑", "美食", "竞技"],
    "4":  ["全部", "冒险", "喜剧", "奇幻", "剧情", "科幻", "动作", "儿童",
           "悬疑", "都市", "家庭", "日常", "爱情", "玄幻", "治愈", "校园"],
    "20": ["全部", "古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
           "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
}

_SORTS = [
    {"n": "按时间", "v": "time"},
    {"n": "按人气", "v": "hits"},
    {"n": "按评分", "v": "score"},
]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    subs = _SUB_CLASS.get(tid, [("全部", tid)])
    FILTERS[tid] = [
        {"key": "class", "name": "分类",
         "value": [{"n": n, "v": ("" if n == "全部" else v)} for n, v in subs]},
        {"key": "area", "name": "地区",
         "value": [{"n": x, "v": ("" if x == "全部" else x)}
                   for x in _AREAS.get(tid, ["全部"])]},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "genre", "name": "剧情",
         "value": [{"n": x, "v": ("" if x == "全部" else x)}
                   for x in _GENRES.get(tid, ["全部"])]},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]


# ===================== 正则（全部对应真实源码） =====================

# ---- 列表卡片（首页/分类页）：ewave-vodlist__thumb + thumb-link ----
_RE_CARD = re.compile(
    r'<div[^>]*class="[^"]*ewave-vodlist__thumb[^"]*"[^>]*?'
    r'title="([^"]*)"[^>]*?'
    r'data-original="([^"]*)"[^>]*?>'
    r'[\s\S]*?'
    r'<span[^>]*class="[^"]*pic-text[^"]*"[^>]*>([^<]*)</span>'
    r'[\s\S]*?'
    r'<a[^>]*class="thumb-link"[^>]*href="([^"]+)"',
    re.S | re.I)

# ---- 搜索卡片（ewave-vodlist__media 结构）----
_RE_SEARCH_CARD = re.compile(
    r'<li[^>]*class="[^"]*active[^"]*"[^>]*>'
    r'[\s\S]*?'
    r'<a[^>]*class="[^"]*v-thumb[^"]*ewave-vodlist__thumb[^"]*"[^>]*?'
    r'href="([^"]+)"[^>]*?'
    r'title="([^"]*)"[^>]*?'
    r'data-original="([^"]*)"[^>]*?>'
    r'[\s\S]*?'
    r'<span[^>]*class="[^"]*pic-text[^"]*"[^>]*>([^<]*)</span>',
    re.S | re.I)

# ---- 详情页 ----
_RE_H1 = re.compile(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_DETAIL_PIC = re.compile(
    r'<div[^>]*class="[^"]*ewave-content__thumb[^"]*"[\s\S]*?'
    r'data-original="([^"]+)"', re.S | re.I)

# 简介：详情页 #desc 里的 <p class="col-pd">
_RE_DESC_FULL = re.compile(
    r'<div[^>]*id="desc"[\s\S]*?<p[^>]*class="[^"]*col-pd[^"]*"[^>]*>([\s\S]*?)</p>',
    re.S | re.I)
# 简介：详情页 .desc 短简介
_RE_DESC_SHORT = re.compile(
    r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>[\s\S]*?简介：</span>([\s\S]*?)<a\s+href="#desc"',
    re.S | re.I)

# 主演/导演（详情页 <p class="data">）
_RE_ACTOR = re.compile(
    r'<span[^>]*class="[^"]*text-muted[^"]*">主演：</span>([\s\S]*?)</p>',
    re.S | re.I)
_RE_DIRECTOR = re.compile(
    r'<span[^>]*class="[^"]*text-muted[^"]*">导演：</span>([\s\S]*?)</p>',
    re.S | re.I)

# 评分：<span class="score text-red raty-score-num">9.0</span>
_RE_SCORE = re.compile(
    r'<span[^>]*class="[^"]*score[^"]*raty-score-num[^"]*"[^>]*>([\d.]+)</span>',
    re.I)

# 选集：<ul class="ewave-content__playlist ..."><li ...><a href="/vodplay/xxx-1-1.html">第01集</a></li>
_RE_PLAYLIST_BLOCK = re.compile(
    r'<ul[^>]*class="[^"]*ewave-content__playlist[^"]*"[^>]*>([\s\S]*?)</ul>',
    re.S | re.I)
_RE_EPISODE = re.compile(
    r'<li[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([^<]*)</a>', re.S | re.I)

# 播放页 player_aaaa
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.S)

# 分页：<span class="num">2/12</span>
_RE_PAGE_NUM = re.compile(r'<span class="num">(\d+)/(\d+)</span>', re.I)


class Spider(Spider):

    def getName(self):
        return "韩国电影网"

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
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------- 基础 ----------
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

    # ---------- 列表解析 ----------
    def _extract_list_videos(self, html):
        """首页/分类页卡片解析"""
        videos = []
        seen = set()
        if not html:
            return videos
        for title, pic, remark, href in _RE_CARD.findall(html):
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(title),
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": self._clean(remark),
            })
        return videos

    def _extract_search_videos(self, html):
        """搜索结果页卡片解析（ewave-vodlist__media 结构）"""
        videos = []
        seen = set()
        if not html:
            return videos
        for href, title, pic, remark in _RE_SEARCH_CARD.findall(html):
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(title),
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": self._clean(remark),
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = _RE_PAGE_NUM.search(html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        return 1

    # ---------- 首页/分类/搜索 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._extract_list_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        # URL 模板（真实）：
        # /vodshow/{分类}-{地区}-{剧情}-{字母}-{排序}-{页码}-{年份}.html
        # 空段留空，段间 '-'。第1页显式写 1。
        tid = str(tid)
        sub = extend.get("class", "") or ""
        if sub:
            tid = str(sub)

        area  = extend.get("area", "") or ""
        genre = extend.get("genre", "") or ""
        sort  = extend.get("sort", "") or ""
        year  = extend.get("year", "") or ""

        area_enc  = urllib.parse.quote(area) if area else ""
        genre_enc = urllib.parse.quote(genre) if genre else ""

        # 7 段：分类-地区-剧情-字母-排序-页码-年份
        url = "%s/vodshow/%s-%s-%s---%s-%d-%s.html" % (
            self.site_url, tid, area_enc, genre_enc, sort, page, year)

        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._extract_list_videos(html)
        pagecount = self._page_count(html)

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 36, "total": pagecount * 36,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        # 真实搜索 URL：/vodsearch/{关键词URL编码}----------{页码}---.html
        kw = urllib.parse.quote(key)
        url = "%s/vodsearch/%s----------%d---.html" % (self.site_url, kw, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_search_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 36, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题：<h1 class="title"><span>老舅</span><span class="score...">2.0</span></h1>
        name = ""
        m = _RE_H1.search(html)
        if m:
            raw = m.group(1)
            # 去掉评分 span
            raw = re.sub(r'<span[^>]*class="[^"]*score[^"]*"[^>]*>[\s\S]*?</span>',
                         "", raw)
            # 取第一个 <span> 内的文本
            ms = re.search(r"<span[^>]*>([\s\S]*?)</span>", raw)
            if ms:
                name = self._clean(ms.group(1))
            if not name:
                name = self._clean(raw)
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_DETAIL_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1))
        else:
            m2 = re.search(r'data-original="(https?://[^"]+/upload/vod/[^"]+)"', html)
            if m2:
                pic = m2.group(1)

        # 简介：优先完整版 #desc，其次 .desc，最后 meta description
        content = ""
        m = _RE_DESC_FULL.search(html)
        if m:
            content = self._clean(m.group(1))
            # 去掉“《xxx》上映于...剧情简介：”之前的套话
            if "剧情简介：" in content:
                content = content.split("剧情简介：", 1)[1]
            elif "剧情:" in content:
                content = content.split("剧情:", 1)[1]
            content = re.sub(r"^[》\s：:]*", "", content).strip()
        if not content:
            m = _RE_DESC_SHORT.search(html)
            if m:
                content = self._clean(m.group(1))
        if not content:
            m = re.search(
                r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
                html, re.I)
            if m:
                content = self._clean(m.group(1))
                content = re.sub(r"^[^：:]*剧情[:：]", "", content).strip()

        content = INTRO_PREFIX + "\n" + content if content else INTRO_PREFIX

        # 主演
        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            names = re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1))
            actor = " ".join(self._clean(x) for x in names if self._clean(x))

        # 导演
        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            names = re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1))
            director = " ".join(self._clean(x) for x in names if self._clean(x))

        # 评分
        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        # 选集（短剧/电视剧/电影都是同一套 ewave-content__playlist）
        episodes = []
        m = _RE_PLAYLIST_BLOCK.search(html)
        if m:
            block = m.group(1)
            for href, ep_name in _RE_EPISODE.findall(block):
                href = href.replace("&amp;", "&")
                if href.startswith("/"):
                    href = self.site_url + href
                episodes.append((self._clean(ep_name) or "播放", href))

        if not episodes:
            return {"list": []}

        play_url = "#".join("%s$%s" % (n, h) for n, h in episodes)

        return {"list": [{
            "vod_id":       vod_id,
            "vod_name":     name,
            "vod_pic":      pic,
            "vod_content":  content,
            "vod_actor":    actor,
            "vod_director": director,
            "vod_score":    score,
            "vod_remarks":  "%d集" % len(episodes) if len(episodes) > 1 else "",
            "vod_play_from": "ffm3u8",
            "vod_play_url":  play_url,
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
        m3u8 = ""
        m = _RE_PLAYER.search(html)
        if m:
            try:
                obj = json.loads(m.group(1))
                m3u8 = obj.get("url", "") or ""
                m3u8 = m3u8.replace("\\/", "/")
            except Exception as e:
                self.log("player_aaaa parse fail: %s" % e)

        if m3u8:
            self.log("  m3u8: %s" % m3u8[:160])
            res = {
                "parse": 0,
                "playUrl": "",
                "url": m3u8,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底：交给 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

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
