# coding=utf-8
"""
麻花影视 ynjcsj.com | TVBox Python 爬虫 (V4.0 终极降维版)
关键:
  - 完美对应网页侧边栏/顶部筛选频道
  - 大类走搜索流兜底，子类走原生静态 HTML
  - 全链路防爬拦截处理
  - player_aaaa.url 直链提取
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
                print("[mahua]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.ynjcsj.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/upload/site/20251221-1/ac2bc08f7f6c858edf82dbb792f7734b.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 完美对应网页左侧/顶部导航栏的频道
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "36", "type_name": "短剧"},
]

_SORTS = [{"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]
_YEARS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_AREAS_TV = [{"n": "全部", "v": ""}, {"n": "内地", "v": "内地"}, {"n": "韩国", "v": "韩国"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"}, {"n": "日本", "v": "日本"}, {"n": "美国", "v": "美国"}, {"n": "泰国", "v": "泰国"}, {"n": "英国", "v": "英国"}, {"n": "新加坡", "v": "新加坡"}, {"n": "其他", "v": "其他"}]
_AREAS_MOVIE = [{"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "法国", "v": "法国"}, {"n": "英国", "v": "英国"}, {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"}, {"n": "德国", "v": "德国"}, {"n": "泰国", "v": "泰国"}, {"n": "印度", "v": "印度"}, {"n": "意大利", "v": "意大利"}, {"n": "西班牙", "v": "西班牙"}, {"n": "加拿大", "v": "加拿大"}, {"n": "其他", "v": "其他"}]

_FILTERS_MAP = {
    "1":  ["全部", "喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪", "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚", "经典", "青春", "文艺", "微电影", "古装", "历史", "运动", "农村", "儿童", "网络电影"],
    "2":  ["全部", "古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
    "3":  ["全部", "选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实", "曲艺", "生活", "游戏互动", "财经", "求职"],
    "4":  ["全部", "情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园", "动作", "机战", "运动", "战争", "少年", "少女", "社会", "原创", "亲子", "益智", "励志", "其他"],
    "36": ["全部", "古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    areas = _AREAS_MOVIE if tid == "1" else _AREAS_TV
    FILTERS[tid] = [
        {"key": "class", "name": "类型", "value": [{"n": x, "v": "" if x == "全部" else x} for x in _FILTERS_MAP.get(tid, ["全部"])]},
        {"key": "area", "name": "地区", "value": areas},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]

# ===================== 正则 =====================
# 静态分类页列表
_RE_CARD = re.compile(
    r'<a class="video-img lazyload"\s+href="(/voddetail/[^"]+)"\s+data-original="([^"]*)"[^>]*>'
    r'[\s\S]{0,400}?'
    r'<span class="video-title[^"]*">([^<]*)</span>'
    r'[\s\S]{0,400}?'
    r'<p class="video-name"><a[^>]*title="([^"]*)"',
    re.S | re.I)

# 搜索页列表
_RE_SEARCH_CARD = re.compile(
    r'<a class="block-fea lazyload"\s+data-original="([^"]*)"\s+href="(/voddetail/[^"]+)"\s+title="([^"]*)"',
    re.S | re.I)

# 详情页解析
_RE_H1 = re.compile(r'<h1 class="detail-info-title[^"]*"><a[^>]*>([\s\S]*?)</a></h1>', re.I)
_RE_DETAIL_PIC = re.compile(r'<article class="post detail-post[^"]*">[\s\S]{0,500}?<div class="block-fea lazyload"\s+data-original="([^"]*)"', re.S | re.I)
_RE_ACTOR = re.compile(r'<span>演员：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_DIRECTOR = re.compile(r'<span>导演：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_STATE = re.compile(r'<span>状态：</span><em[^>]*>([^<]*)</em>', re.I)
_RE_SCORE = re.compile(r'<h4 class="ewave-star-num[^"]*">([\d.]+)</h4>', re.I)
_RE_INTRO = re.compile(r'<div class="entry-content clearfix">([\s\S]*?)</div>', re.S | re.I)

# 剧集列表解析
_RE_TAB = re.compile(r'<li class="swiper-slide ewave-tab[^"]*" data-target="#(ewave-playlist-\d+)"><a[^>]*>([^<]*)</a></li>', re.I)
_RE_PLAYLIST = re.compile(r'<ul[^>]*id="(ewave-playlist-\d+)"[^>]*>([\s\S]*?)</ul>', re.S | re.I)
_RE_EP = re.compile(r'<a class="text-overflow"\s+href="(/vodplay/[^"]+)">([^<]*)</a>', re.I)

# 播放器解析
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.S)


class Spider(Spider):

    def getName(self):
        return "麻花影视"

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
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html: return videos
        for m in _RE_CARD.finditer(html):
            href, pic, remark, name = m.groups()
            if href in seen: continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(name)[:100],
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": self._clean(remark),
            })
        return videos

    def _extract_search_videos(self, html):
        videos = []
        seen = set()
        if not html: return videos
        for m in _RE_SEARCH_CARD.finditer(html):
            pic, href, name = m.groups()
            if href in seen: continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(name)[:100],
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html: return 1
        m = re.search(r'<span class="hidden-sm hidden-md hidden-lg">/(\d+)</span>', html)
        if m:
            try: return int(m.group(1))
            except Exception: pass
        return 1

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try: extend = json.loads(extend)
            except Exception: extend = {}
        if not extend: extend = {}

        area = extend.get("area") or ""
        cls  = extend.get("class") or ""
        year = extend.get("year") or ""

        videos = []
        html = ""

        # 1. 原生静态子分类直连（有数据，且无筛选时最稳）
        if tid not in ("1", "2", "3", "4") and not area and not cls and not year and page == 1:
            url = "%s/vodtype/%s.html" % (self.site_url, tid)
            self.log("category (原生页): %s" % url)
            html = self._fetch(url)
            videos = self._extract_videos(html)

        # 2. 走 /vodshow/ 路径（标准模板，能正常返回静态数据的情况下）
        if not videos:
            url = "%s/vodshow/%s-%s-%s-%s-%s-%s-%s-%s-%s-time.html" % (
                self.site_url, tid, area, cls, "", "", "", "", year, page)
            self.log("category (筛选页): %s" % url)
            html = self._fetch(url)
            videos = self._extract_videos(html)

        # 3. 终极兜底（如果上面都被 Ajax 防爬拦截了，搜索流直接干）
        if not videos:
            self.log("  ⚠️ 页面被防爬拦截，启用搜索流")
            wd = cls or year or area or ""
            url2 = "%s/vodsearch/-------------.html?wd=%s&page=%d" % (self.site_url, urllib.parse.quote(wd), page)
            self.log("  (搜索兜底): %s" % url2)
            html2 = self._fetch(url2)
            videos = self._extract_search_videos(html2)
            html = html2

        pagecount = self._page_count(html)
        if pagecount == 1 and videos:
            pagecount = 999  # 搜索兜底情况允许无限翻页

        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/vodsearch/-------------.html?wd=%s&page=%d" % (self.site_url, keyword, page)
        html = self._fetch(url)
        videos = self._extract_search_videos(html)
        return {
            "list": videos, "page": page, "pagecount": self._page_count(html),
            "limit": 24, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids: return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
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
        if m: pic = self._fix_url(m.group(1)) or self.default_pic

        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            actor = self._clean(re.sub(r"</a>", "", m.group(1)))
            actor = re.sub(r"\s+", ",", actor).strip(",")

        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            director = self._clean(re.sub(r"</a>", "", m.group(1)))
            director = re.sub(r"\s+", ",", director).strip(",")

        state = ""
        m = _RE_STATE.search(html)
        if m: state = self._clean(m.group(1))

        score = ""
        m = _RE_SCORE.search(html)
        if m: score = m.group(1)

        content = ""
        m = _RE_INTRO.search(html)
        if m: content = self._clean(m.group(1))
        content = INTRO_PREFIX + ("\n" + content if content else "")

        tab_map = {}
        for m in _RE_TAB.finditer(html):
            tab_map[m.group(1)] = self._clean(m.group(2)) or "线路"

        lines = []
        for m in _RE_PLAYLIST.finditer(html):
            pid, inner = m.group(1), m.group(2)
            eps = []
            for em in _RE_EP.finditer(inner):
                href, ep_name = em.group(1), self._clean(em.group(2))
                eps.append("%s$%s" % (ep_name, self._fix_url(href)))
            if eps: lines.append((tab_map.get(pid, pid), eps))

        if not lines: return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": state or ("%d条线路" % len(lines)),
            "vod_play_from": "$$$".join(x[0] for x in lines),
            "vod_play_url":  "$$$".join("#".join(x[1]) for x in lines),
        }]}

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600: return res

        html = self._fetch(play_page)
        real_url = self._extract_player_url(html)

        if real_url:
            res = {
                "parse": 0,
                "playUrl": "",
                "url": real_url,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
        else:
            res = {
                "parse": 1,
                "playUrl": "",
                "url": play_page,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
            
        self._play_cache[play_page] = (now, res)
        return res

    def _extract_player_url(self, html):
        if not html: return ""
        m = _RE_PLAYER.search(html)
        if not m: return ""
        raw = m.group(1)
        try:
            data = json.loads(raw)
            url = data.get("url") or ""
            return url.replace("\\/", "/")
        except Exception:
            m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            if m2: return m2.group(1).replace("\\/", "/")
            return ""

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
