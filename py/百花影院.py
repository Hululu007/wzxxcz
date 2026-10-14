# coding=utf-8
"""
百花影院 yctd.cc | TVBox Python 爬虫
网站结构：
  - 列表卡片: article.paper-card > a.paper-cover[href=/video/{id}.html]
              img[data-src=封面] + span.score-tag + span.duration
  - 详情: h1 标题 / .detail-poster-wrap img[src] / .detail-meta / .description
          选集: div.play-source > div.episode-list > a[href=/player/{vid}-{sid}-{nid}.html]
  - 分类分页: /category/{tid}-{pg}.html  (尾页在 nav.pagination 的“尾页”)
  - 分类筛选: /vodshow/{tid}-{area}-{order}-{class}-{lang}-{letter}-{year}.html
              段位固定 7 段，空段用空串占位
  - 搜索: /search.html?wd=关键词  (+ &page=N 翻页)
  - 播放: <script>var player_aaaa={...,"url":"m3u8直链","from":"1080zyk",...}</script>
          走直链：直接返回 player_aaaa.url
"""
import re
import sys
import json
import time
import base64
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
                print("[yctd]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://yctd.cc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/frost/asset/img/placeholder.svg"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ============ 分类（依据 nav 真实结构，含子类 id） ============
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "25", "type_name": "短剧"},
]

_SUB_CLASS = {
    "1":  [("全部", "1"), ("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"),
           ("科幻片", "9"), ("恐怖片", "10"), ("剧情片", "11"), ("战争片", "12")],
    "2":  [("全部", "2"), ("国产剧", "13"), ("港台剧", "14"),
           ("日韩剧", "15"), ("欧美剧", "16")],
    "3":  [("全部", "3")],
    "4":  [("全部", "4"), ("国产", "20"), ("日韩", "21"),
           ("欧美", "22"), ("港台", "23"), ("海外", "24")],
    "25": [("全部", "25"), ("玄幻", "26"), ("仙侠", "27"), ("刑侦", "28"),
           ("历史", "29"), ("权谋", "30"), ("宫斗", "31"), ("爱情", "32"),
           ("喜剧", "36"), ("战神", "37"), ("冒险", "35"), ("武侠", "34"),
           ("商战", "33"), ("悬疑", "38"), ("剧情", "39"), ("豪门", "40"),
           ("动作", "41"), ("求生", "42"), ("科幻", "43"), ("齐幻", "44"),
           ("女性", "45")],
}

_TYPE_OPT = {
    "1":  ["全部", "喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争",
           "警匪", "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑",
           "惊悚", "经典", "青春", "文艺", "微电影", "古装", "历史", "运动",
           "农村", "儿童", "网络电影"],
    "2":  ["全部", "国产", "港台", "日韩", "欧美", "泰国", "海外"],
    "3":  ["全部", "真人秀", "脱口秀", "国产综艺", "喜剧", "晚会", "音乐",
           "纪录", "游戏", "生活", "文化", "相声", "情感", "竞技"],
    "4":  ["全部", "国产", "日韩", "欧美", "港台", "海外", "动画", "冒险",
           "喜剧", "奇幻", "剧情", "科幻", "动作", "儿童", "悬疑", "日常"],
    "25": ["全部", "AI漫剧", "短剧", "剧情", "爱情", "爽文", "古装", "短片",
           "悬疑", "喜剧", "奇幻", "都市", "玄幻", "犯罪", "家庭", "穿越",
           "惊悚", "武侠", "科幻", "动作", "冒险", "恐怖", "青春", "历史"],
}

_YEARS = ["全部"] + [str(y) for y in range(2026, 2009, -1)]
_AREAS = ["全部", "大陆", "香港", "台湾", "美国", "日本", "韩国",
          "英国", "法国", "加拿大", "印度", "泰国", "其它"]
_SORTS = [("更新", "time"), ("热度", "hits"), ("评分", "score")]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "类型",
         "value": [{"n": x, "v": "" if x == "全部" else x}
                   for x in _TYPE_OPT.get(tid, ["全部"])]},
        {"key": "sub", "name": "子类",
         "value": [{"n": n, "v": "" if n == "全部" else v}
                   for n, v in _SUB_CLASS.get(tid, [("全部", tid)])]},
        {"key": "area", "name": "地区",
         "value": [{"n": x, "v": "" if x == "全部" else x} for x in _AREAS]},
        {"key": "year", "name": "年份",
         "value": [{"n": x, "v": "" if x == "全部" else x} for x in _YEARS]},
        {"key": "order", "name": "排序",
         "value": [{"n": n, "v": v} for n, v in _SORTS]},
    ]


# ===================== 正则 =====================
# 卡片：完整 article
_RE_CARD = re.compile(
    r'<article class="paper-card[^"]*">([\s\S]*?)</article>',
    re.S | re.I)
_RE_CARD_HREF = re.compile(r'href="(/video/\d+\.html)"', re.I)
_RE_CARD_TITLE = re.compile(r'title="([^"]*)"', re.I)
_RE_CARD_IMG = re.compile(
    r'<img[^>]*?(?:data-src|src)="([^"]+)"[^>]*?>', re.S | re.I)
_RE_CARD_SCORE = re.compile(r'<span class="score-tag">([^<]*)</span>', re.I)
_RE_CARD_DUR = re.compile(r'<span class="duration">([^<]*)</span>', re.I)

# 详情
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_POSTER = re.compile(
    r'<a class="detail-poster-wrap"[^>]*>\s*<img[^>]*?src="([^"]+)"',
    re.S | re.I)
_RE_META = re.compile(r'<p class="detail-meta">([\s\S]*?)</p>', re.I)
_RE_DESC = re.compile(r'<p class="description">([\s\S]*?)</p>', re.I)
_RE_CAST = re.compile(
    r'<p class="cast[^"]*"><span>([^<]+)：</span><em>([\s\S]*?)</em></p>',
    re.S | re.I)

# 选集：div.play-source -> h3 + div.episode-list -> a
_RE_PLAY_SOURCE = re.compile(
    r'<div class="play-source">\s*<h3>([^<]*)</h3>\s*'
    r'<div class="episode-list">([\s\S]*?)</div>\s*</div>',
    re.S | re.I)
_RE_EP = re.compile(
    r'<a[^>]*href="(/player/[^"]+\.html)"[^>]*>([^<]*)</a>', re.I)

# 分页
_RE_PAGINATION = re.compile(
    r'<nav class="pagination">([\s\S]*?)</nav>', re.S | re.I)
_RE_PAGE_NUM = re.compile(r'href="(/category/\d+-(\d+)\.html)"', re.I)

# player_aaaa
_RE_PLAYER = re.compile(
    r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)


class Spider(Spider):

    def getName(self):
        return "百花影院"

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

    # ---------- 列表解析 ----------
    def _parse_cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        for block in _RE_CARD.findall(html):
            mh = _RE_CARD_HREF.search(block)
            if not mh:
                continue
            href = mh.group(1)
            if href in seen:
                continue
            seen.add(href)

            mt = _RE_CARD_TITLE.search(block)
            name = self._clean(mt.group(1)) if mt else ""
            if not name:
                mt2 = re.search(r'<h3[^>]*><a[^>]*>([^<]+)</a>', block, re.I)
                if mt2:
                    name = self._clean(mt2.group(1))

            mi = _RE_CARD_IMG.search(block)
            pic = ""
            if mi:
                pic = mi.group(1)
                if pic.endswith("placeholder.svg"):
                    md = re.search(r'data-src="([^"]+)"', block, re.I)
                    if md:
                        pic = md.group(1)
            pic = self._fix_url(pic) or DEFAULT_PIC

            ms = _RE_CARD_SCORE.search(block)
            score = ms.group(1).strip() if ms else ""
            md2 = _RE_CARD_DUR.search(block)
            remarks = md2.group(1).strip() if md2 else ""
            if not remarks and score:
                remarks = score

            videos.append({
                "vod_id": href,
                "vod_name": name or href,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return videos

    def _parse_pagination(self, html, tid):
        if not html:
            return 1
        mp = _RE_PAGINATION.search(html)
        if not mp:
            return 1
        nums = [int(n) for _, n in _RE_PAGE_NUM.findall(mp.group(1))]
        if not nums:
            return 1
        return max(nums)

    # ---------- TVBox 接口 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML len=%d" % len(html))
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
        cls = extend.get("class") or ""
        area = extend.get("area") or ""
        year = extend.get("year") or ""
        order = extend.get("order") or "time"

        has_filter = bool(cls or area or year or (order and order != "time"))
        if not has_filter:
            real_tid = sub or tid
            url = "%s/category/%s-%d.html" % (self.site_url, real_tid, page)
        else:
            t = sub or tid

            def enc(x):
                return urllib.parse.quote(x) if x else ""

            seg = [t, enc(area), order or "", enc(cls), "", "", enc(year)]
            url = "%s/vodshow/%s.html" % (self.site_url, "-".join(seg))
            if page > 1:
                url += "?page=%d" % page

        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  html len=%d" % len(html))
        videos = self._parse_cards(html)
        pagecount = self._parse_pagination(html, tid) if not has_filter else page
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        url = "%s/search.html?wd=%s" % (self.site_url, kw)
        if page > 1:
            url += "&page=%d" % page
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
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            mt = re.search(r"<title>(.*?)</title>", html, re.S)
            if mt:
                name = self._clean(mt.group(1).split("-")[0])
        name = name or vod_id

        # 封面
        pic = DEFAULT_PIC
        m = _RE_POSTER.search(html)
        if m:
            pic = self._fix_url(m.group(1))
        if not pic or pic.endswith("placeholder.svg"):
            m2 = re.search(r'<img[^>]*src="(https?://[^"]+)"', html)
            if m2:
                pic = m2.group(1)

        # 元信息
        score = ""
        year = area = type_name = ""
        m = _RE_META.search(html)
        if m:
            raw = self._clean(m.group(1))
            parts = [p.strip() for p in raw.split() if p.strip()]
            for p in parts:
                if "分" in p and re.match(r"^[\d.]+分?$", p.replace("分", "分")):
                    score = p.replace("分", "")
                elif re.match(r"^(19|20)\d{2}$", p):
                    year = p
                elif not area:
                    area = p
                elif not type_name:
                    type_name = p

        # 简介
        content = ""
        m = _RE_DESC.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            md = re.search(
                r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
                html, re.I)
            if md:
                content = self._clean(md.group(1))

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # 导演 / 主演
        director = actor = ""
        for label, val in _RE_CAST.findall(html):
            v = self._clean(val)
            if v in ("未知", "演员资料待补充"):
                v = ""
            if "导演" in label:
                director = v
            elif "主演" in label:
                actor = re.sub(r"\s*,\s*", ", ", v)

        # 选集
        groups = []
        for line_name, ep_block in _RE_PLAY_SOURCE.findall(html):
            eps = []
            for ep_href, ep_name in _RE_EP.findall(ep_block):
                ep_href = ep_href.replace("&amp;", "&")
                eps.append((self._clean(ep_name) or "播放",
                            self._fix_url(ep_href)))
            if eps:
                groups.append((self._clean(line_name) or "线路", eps))

        if not groups:
            return {"list": []}

        play_from = [g[0] for g in groups]
        play_url = ["#".join("%s$%s" % (n, h) for n, h in g[1]) for g in groups]

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_year": year,
            "vod_area": area,
            "vod_remarks": ("%d条线路" % len(groups)) if groups else "",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ---------- 播放（走直链）----------
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
        from_flag = ""

        m = _RE_PLAYER.search(html)
        if m:
            raw = m.group(1)
            try:
                info = json.loads(raw)
            except Exception:
                info = {}
                m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if m2:
                    info["url"] = m2.group(1)
                m2 = re.search(r'"from"\s*:\s*"([^"]+)"', raw)
                if m2:
                    info["from"] = m2.group(1)
                m2 = re.search(r'"encrypt"\s*:\s*"?(\d+)"?', raw)
                if m2:
                    info["encrypt"] = int(m2.group(1))

            play_url = (info.get("url", "") or "").replace("\\/", "/")
            play_url = play_url.replace("&amp;", "&")
            from_flag = info.get("from", "") or ""
            encrypt = info.get("encrypt", 0)

            # 与 player.js 的 encrypt 处理保持一致
            if encrypt == 1:
                play_url = urllib.parse.unquote(play_url)
            elif encrypt == 2:
                try:
                    play_url = base64.b64decode(play_url).decode(
                        "utf-8", "ignore")
                    play_url = urllib.parse.unquote(play_url)
                except Exception as e:
                    self.log("encrypt=2 decode fail: %s" % e)

        # 走直链：直接把 m3u8 地址交给 TVBox 播放
        if play_url:
            self.log("  direct: %s" % play_url[:200])
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
