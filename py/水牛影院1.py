# coding=utf-8
"""
水牛影院 sunnykings.com | TVBox Python 爬虫
结构说明（全部基于网站 2026 真实源码实测）：
  - 苹果CMS(stui模板)站，分类页 /listnew/{id}.html，翻页 /listnew/{id}-{pg}.html
  - 详情页支持 /cp/{id}.html、/m/{id}.html、/wap/{id}.html、/tv/{x}/{y}.html
  - 剧集: <li><a href="/tvplay/{id}-{sid}-{nid}.html">第01集</a></li>，按线路分块，线路名在 title">xxx</h3>
  - 播放页: var player_aaaa={"flag":"play","encrypt":0,"url":"https://cdn.xxx/index.m3u8",...} 直链 m3u8
  - 搜索: /search/-------------.html?wd=关键词(URLEncode)，结果卡片 /m/{id}.html
  - 卡片: <a href="/xxx/{id}.html" title="片名" data-original="海报">
"""
import re
import sys
import json
import time
import html as _html
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
                print("[shuiniu]", *a, **kw)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.sunnykings.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 首页导航真实分类（源码 /listnew/ 链接与文字一一对应）
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "30", "type_name": "爽文短剧"},
]

# 二级筛选：来自分类页 <ul class="stui-screen__list type-slide"> 里的 /so-show/{tid}-{class}-{area}-{year}... 链接
# 网站筛选 URL 格式: /so-show/{tid}-{class}-{area}-{lang}-{year}-----------.html (横线占位)
SORTS = [
    {"n": "最新", "v": "time"},
    {"n": "最热", "v": "score"},
]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)]

AREAS_BY_TID = {
    "1": ["全部", "大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
          "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
    "2": ["全部", "大陆", "香港", "台湾", "韩国", "日本", "美国", "泰国", "英国",
          "新加坡", "其他"],
    "3": ["全部", "大陆", "香港", "台湾", "日本", "韩国", "美国", "其他"],
    "4": ["全部", "大陆", "日本", "美国", "韩国", "其他"],
    "30": ["全部"],
}
_CLASSES_BY_TID = {
    "1": ["全部", "动作片", "喜剧片", "爱情片", "科幻片", "恐怖片", "剧情片",
          "战争片", "犯罪片"],
    "2": ["全部", "国产剧", "港剧", "台湾剧", "韩剧", "日剧", "欧美剧", "海外剧"],
    "3": ["全部", "大陆综艺", "日韩综艺", "港台综艺", "欧美综艺"],
    "4": ["全部", "国产动漫", "日本动漫", "欧美动漫", "海外动漫"],
    "30": ["全部"],
}


def _build_filters():
    filters = {}
    for c in CLASSES:
        tid = c["type_id"]
        filters[tid] = [
            {"key": "class", "name": "类型",
             "value": [{"n": x, "v": "" if x == "全部" else x}
                       for x in _CLASSES_BY_TID.get(tid, ["全部"])]},
            {"key": "area", "name": "地区",
             "value": [{"n": x, "v": "" if x == "全部" else x}
                       for x in AREAS_BY_TID.get(tid, ["全部"])]},
            {"key": "year", "name": "年份", "value": _YEARS},
        ]
    return filters


FILTERS = _build_filters()


# ===================== 正则（与真实源码逐字对齐） =====================
# 卡片: href="/cp/99488.html" title="恋爱沙尘暴" data-original="/upload/vod/...jpg"
_RE_CARD = re.compile(
    r'href="(/(?:tv|cp|m|wap)/[^"]+?\.html)"[^>]*?title="([^"]*)"[^>]*?'
    r'data-original="([^"]*)"',
    re.S | re.I)

# 分页最大页: /listnew/2-978.html
_RE_PAGE = re.compile(r'href="/listnew/\d+-(\d+)\.html"')

# 详情页 <title>《恋爱沙尘暴》电视剧在线观看 -... -水牛影院
_RE_TITLE_BOOK = re.compile(r'《(.+?)》')
_RE_TITLE_TAG = re.compile(r'<title>(.*?)</title>', re.S)
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_PIC = re.compile(r'data-original="([^"]+)"', re.I)

# 简介块: <span class="... detail-sketch">　　...</span>
_RE_INTRO = re.compile(
    r'<span[^>]*class="[^"]*detail-sketch[^"]*"[^>]*>([\s\S]*?)</span>', re.I)

# 评分: <span class="... branch">7.0</span>
_RE_SCORE = re.compile(r'branch">([\d.]+)\s*</span>', re.I)

# 主演/导演段落: <p class="... data ..."><span ...>主演：</span><a ...>吴慷仁</a>...</p>
_RE_CAST_P = re.compile(
    r'<p[^>]*class="[^"]*data[^"]*"[^>]*>\s*<span[^>]*>(主演|导演)：?</span>([\s\S]*?)</p>', re.I)
_RE_CAST_A = re.compile(r'<a[^>]*>([^<]+)</a>')

# 线路名: <h3 class="... title">1080zyk</h3>
_RE_SOURCE = re.compile(r'title">([^<]+)</h3>', re.I)
# 每条线路的剧集块
_RE_PLAYLIST = re.compile(
    r'stui-content__playlist[\s\S]*?</ul>', re.I)
_RE_EP = re.compile(r'<a\s+href="([^"]+)"[^>]*>([\s\S]*?)</a>')

# 播放页 player_aaaa（真实源码: var player_aaaa={...};）
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.S)


class Spider(Spider):

    def getName(self):
        return "水牛影院"

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
        self.log("init: %s" % self.site_url)

    # ---------------- 基础 ----------------
    def _fetch(self, url, timeout=30):
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _fix_url(self, u):
        if not u:
            return ""
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        if u.startswith("/"):
            return self.site_url + u
        return urllib.parse.urljoin(self.site_url + "/", u)

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        try:
            s = _html.unescape(s)
        except Exception:
            pass
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        for href, title, pic in _RE_CARD.findall(html):
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            name = self._clean(title)
            if not name:
                continue
            videos.append({
                "vod_id": href,
                "vod_name": name[:100],
                "vod_pic": self._fix_url(pic),
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        pages = _RE_PAGE.findall(html or "")
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        return 1

    # ---------------- TVBox 接口 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        cls = extend.get("class") or ""
        area = extend.get("area") or ""
        year = extend.get("year") or ""

        if cls or area or year:
            # 真实筛选 URL: /so-show/{tid}-{class}-{area}-{lang}-{year}-----------.html
            url = "%s/so-show/%s-%s-%s----%s-----------.html" % (
                self.site_url, tid, cls, area, year)
            if page > 1:
                url = "%s/so-show/%s-%s-%s----%s----------%d---.html" % (
                    self.site_url, tid, cls, area, year, page)
        else:
            if page > 1:
                url = "%s/listnew/%s-%d.html" % (self.site_url, tid, page)
            else:
                url = "%s/listnew/%s.html" % (self.site_url, tid)

        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  %d 条, 总页数 %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        keyword = urllib.parse.quote(key)
        if page > 1:
            url = "%s/search/-%s----------%d---.html" % (
                self.site_url, keyword, page)
        else:
            url = "%s/search/-------------.html?wd=%s" % (
                self.site_url, keyword)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": page if videos else 1,
            "limit": 24, "total": 24 * page if videos else 0,
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

        # 标题: <title>《恋爱沙尘暴》电视剧在线观看...
        name = ""
        m = _RE_TITLE_BOOK.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_H1.search(html)
            if m:
                name = self._clean(m.group(1))
        if not name:
            m = _RE_TITLE_TAG.search(html)
            if m:
                name = self._clean(m.group(1).split("_")[0])
        name = name or vod_id

        # 封面（详情页首个 data-original 即海报）
        pic = ""
        m = _RE_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        # 简介: <span class="... detail-sketch">
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(
                r'<meta[^>]*name="description"[^>]*content="([^"]*)"',
                html, re.I)
            if m:
                # meta 形如 "恋爱沙尘暴剧情简介:　　..."
                content = self._clean(m.group(1))
                content = re.sub(r'^.*?剧情简介[:：]?', '', content)

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # 评分
        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        # 主演/导演
        actor, director = "", ""
        for m in _RE_CAST_P.finditer(html):
            role, seg = m.group(1), m.group(2)
            names = [self._clean(x) for x in _RE_CAST_A.findall(seg)]
            names = [x for x in names if x]
            if role == "主演" and not actor:
                actor = ", ".join(names)
            elif role == "导演" and not director:
                director = ", ".join(names)

        # 剧集: 每个 title">线路名</h3> 后跟一个 stui-content__playlist 块
        play_from, play_url = [], []
        sources = [(m.start(), m.group(1).strip())
                   for m in _RE_SOURCE.finditer(html)]
        blocks = [(m.start(), m.group(0))
                  for m in _RE_PLAYLIST.finditer(html)]
        for pos, src in sources:
            block = None
            for bpos, bhtml in blocks:
                if bpos > pos:
                    block = bhtml
                    break
            if not block:
                continue
            eps = []
            for ep_href, ep_name in _RE_EP.findall(block):
                ep_name = self._clean(ep_name)
                if not ep_name or not ep_href:
                    continue
                ep_href = ep_href.replace("&amp;", "&")
                if ep_href.startswith("/"):
                    ep_href = self.site_url + ep_href
                eps.append("%s$%s" % (ep_name, ep_href))
            if eps:
                play_from.append(src)
                play_url.append("#".join(eps))

        self.log("  线路: %s" % play_from)
        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": "%d条线路" % len(play_from),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------------- 播放 ----------------
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
        if html:
            m = _RE_PLAYER.search(html)
            if m:
                try:
                    data = json.loads(m.group(1))
                    m3u8 = (data.get("url") or "").replace("\\/", "/")
                except Exception:
                    m2 = re.search(r'"url"\s*:\s*"([^"]+)"', m.group(1))
                    if m2:
                        m3u8 = m2.group(1).replace("\\/", "/")

        if m3u8 and "://" in m3u8:
            self.log("  => %s" % m3u8[:160])
            res = {
                "parse": 0,
                "playUrl": "",
                "url": m3u8,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
        else:
            # 兜底交给 TVBox 嗅探
            res = {
                "parse": 1,
                "playUrl": "",
                "url": play_page,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
        self._play_cache[play_page] = (now, res)
        return res

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [200, "image/jpeg", b"", ""]

    def destroy(self):
        pass

    def close(self):
        self.destroy()
