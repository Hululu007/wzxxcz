# coding=utf-8
"""
欧洲影院 51shuoshuo.com | TVBox Python 爬虫 
关键:
  - 苹果CMS v10 + ewave 模板
  - 完美解析 分类/地区/年份/导演/主演/状态 到标准字段
  - 简介多级兜底: 支持剧情简述/剧情脉络/简介等所有变体
  - 播放页 player_aaaa encrypt=0 直接取 m3u8
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
                print("[51shuoshuo]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.51shuoshuo.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/ewave-orange/images/load.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺片"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "24", "type_name": "短剧"},
]

_SUB_CLASS = {
    "1": [("全部", ""), ("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"), ("科幻片", "9"), ("剧情片", "10"), ("战争片", "11"), ("动画片", "41"), ("记录片", "12"), ("恐怖片", "39")],
    "2": [("全部", ""), ("国产剧", "13"), ("香港剧", "14"), ("韩国剧", "15"), ("欧美剧", "16"), ("台湾剧", "22"), ("日本剧", "21"), ("泰国剧", "20"), ("海外剧", "23")],
    "3": [("全部", ""), ("大陆综艺", "25"), ("日韩综艺", "26"), ("港台综艺", "27"), ("欧美综艺", "28")],
    "4": [("全部", ""), ("国产动漫", "29"), ("日本动漫", "30"), ("港台动漫", "42"), ("欧美动漫", "31"), ("海外动漫", "43")],
    "24": [("全部", ""), ("短剧大全", "40"), ("AI漫剧", "44")],
}

_AREAS_MOVIE = ["全部", "大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"]
_AREAS_TV    = ["全部", "内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"]
_AREAS_SHOW  = ["全部", "内地", "港台", "日韩", "欧美"]
_AREAS_ANIME = ["全部", "国产", "日本", "欧美", "其他"]
_AREAS_DUANJU= ["全部", "大陆", "香港", "台湾", "美国", "韩国", "日本", "泰国", "新加坡", "马来西亚", "印度", "英国", "法国", "加拿大", "西班牙", "俄罗斯", "其它"]

_YEARS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_SORTS = [{"n": "最近更新", "v": "time"}, {"n": "最多播放", "v": "hits"}, {"n": "最好评", "v": "score"}]

FILTERS = {
    "1": [{"key": "class", "name": "分类", "value": [{"n": n, "v": v} for n, v in _SUB_CLASS["1"]]}, {"key": "area", "name": "地区", "value": [{"n": a, "v": "" if a=="全部" else a} for a in _AREAS_MOVIE]}, {"key": "year", "name": "年份", "value": _YEARS}, {"key": "by", "name": "排序", "value": _SORTS}],
    "2": [{"key": "class", "name": "分类", "value": [{"n": n, "v": v} for n, v in _SUB_CLASS["2"]]}, {"key": "area", "name": "地区", "value": [{"n": a, "v": "" if a=="全部" else a} for a in _AREAS_TV]}, {"key": "year", "name": "年份", "value": _YEARS}, {"key": "by", "name": "排序", "value": _SORTS}],
    "3": [{"key": "class", "name": "分类", "value": [{"n": n, "v": v} for n, v in _SUB_CLASS["3"]]}, {"key": "area", "name": "地区", "value": [{"n": a, "v": "" if a=="全部" else a} for a in _AREAS_SHOW]}, {"key": "year", "name": "年份", "value": _YEARS}, {"key": "by", "name": "排序", "value": _SORTS}],
    "4": [{"key": "class", "name": "分类", "value": [{"n": n, "v": v} for n, v in _SUB_CLASS["4"]]}, {"key": "area", "name": "地区", "value": [{"n": a, "v": "" if a=="全部" else a} for a in _AREAS_ANIME]}, {"key": "year", "name": "年份", "value": _YEARS}, {"key": "by", "name": "排序", "value": _SORTS}],
    "24": [{"key": "class", "name": "分类", "value": [{"n": n, "v": v} for n, v in _SUB_CLASS["24"]]}, {"key": "area", "name": "地区", "value": [{"n": a, "v": "" if a=="全部" else a} for a in _AREAS_DUANJU]}, {"key": "year", "name": "年份", "value": _YEARS}, {"key": "by", "name": "排序", "value": _SORTS}],
}

# ===================== 正则 =====================
_RE_CARD = re.compile(
    r'<a\s+href="(/p/\d+\.html)"\s+title="([^"]*)"[^>]*>'
    r'[\s\S]{0,300}?'
    r'(?:data-original|data-src|src)="([^"]*)"',
    re.S | re.I)

_RE_PAGE_NUM = re.compile(r'num">(\d+)/(\d+)<')
_RE_H3_TITLE = re.compile(r'<h3[^>]*>\s*<a[^>]*>([\s\S]*?)</a>', re.I)
_RE_PIC = re.compile(r'<div class="pic">[\s\S]{0,200}?(?:data-original|data-src|src)="([^"]+)"', re.I)

# 元信息 (干干净净提取纯文本)
_RE_META_BLOCK = re.compile(r'<p class="row">([\s\S]*?)</p>', re.I)
_RE_DIR = re.compile(r'导演：([^<]+)', re.I)
_RE_ACT = re.compile(r'主演：([^<]+)', re.I)
_RE_STAT = re.compile(r'状态：([^<\s]+)', re.I)

# 简介多级兜底 (兼容 剧情简述 / 情节简介 / 剧情脉络)
_RE_INTRO_LONG = re.compile(r'<h2>[^<]*?(?:剧情|简介)[^<]*?</h2>[\s\S]{0,300}?<p[^>]*>([\s\S]*?)</div>', re.I)
_RE_INTRO_SHORT = re.compile(r'<div class="text text-row[^"]*">\s*简介：([\s\S]*?)</div>', re.I)

# 剧集列表
_RE_TAB = re.compile(r'<li class="[^"]*ewave-tab[^"]*"\s+data-target="#ewave-playlist-(\d+)">\s*([^<]*?)\s*<em>', re.I)
_RE_PLAYLIST_UL = re.compile(r'<ul[^>]*id="ewave-playlist-(\d+)"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_EP_A = re.compile(r'<a[^>]*href="(/player/\d+/\d+/\d+\.html)"[^>]*>([^<]*)</a>', re.I)

_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\});?\s*</script>', re.I)


class Spider(Spider):

    def getName(self):
        return "欧洲影院"

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
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=30, headers=None):
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

    def _extract_videos(self, html):
        videos, seen = [], set()
        if not html:
            return videos

        for href, title, pic in _RE_CARD.findall(html):
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(title)[:100],
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        m = _RE_PAGE_NUM.search(html or "")
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        return 1

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
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

        def _v(k):
            v = extend.get(k)
            return "" if v in ("", None, "全部") else v

        area, cls, by, year = _v("area"), _v("class"), _v("by") or "time", _v("year")
        
        cat_id = tid
        if cls:
            if cls.isdigit():
                cat_id = cls
            else:
                for n, v in _SUB_CLASS.get(tid, []):
                    if v and (cls == n or cls == v):
                        cat_id = v
                        break

        seg = ["set"]
        if area: seg += ["area", urllib.parse.quote(area)]
        if by:   seg += ["by", by]
        seg += ["id", cat_id]
        if page > 1: seg += ["page", str(page)]
        if year: seg += ["year", str(year)]
        
        url = self.site_url + "/" + "/".join(seg) + ".html"
        self.log("category: %s" % url)
        html = self._fetch(url)
        
        return {
            "list": self._extract_videos(html), 
            "page": page, 
            "pagecount": self._page_count(html),
            "limit": 24, 
            "total": 9999,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/scan2.html?wd=%s" % (self.site_url, keyword)
        if page > 1: url += "&page=%d" % page
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
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = _RE_H3_TITLE.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1)) or self.default_pic

        # 元信息：导演、演员、状态
        director, actor, remarks = "", "", ""
        meta_html = _RE_META_BLOCK.search(html)
        target_html = meta_html.group(1) if meta_html else html

        m = _RE_DIR.search(target_html)
        if m: director = self._clean(m.group(1))
        m = _RE_ACT.search(target_html)
        if m: actor = re.sub(r"\s*,\s*", ", ", self._clean(m.group(1)))
        # 副标题（状态）全局匹配
        m = _RE_STAT.search(html)
        if m: remarks = self._clean(m.group(1))

        # 简介
        content = ""
        m = _RE_INTRO_LONG.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_INTRO_SHORT.search(html)
            if m:
                content = self._clean(m.group(1))
        if not content:
            m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.I)
            if m:
                content = self._clean(m.group(1))

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # ===== 剧集提取 =====
        tab_names = {}
        for sid, tname in _RE_TAB.findall(html):
            tab_names[sid] = self._clean(tname) or ("线路%s" % sid)

        groups = {}
        for sid, body in _RE_PLAYLIST_UL.findall(html):
            eps = []
            for href, ep in _RE_EP_A.findall(body):
                href = href.replace("&amp;", "&")
                ep = self._clean(ep) or ("第%d集" % (len(eps) + 1))
                eps.append((ep, href))
            if eps:
                groups[sid] = eps

        self.log("  剧集: %s" % {k: len(v) for k, v in groups.items()})

        if not groups:
            return {"list": []}

        ordered_sids = [sid for sid in tab_names.keys() if sid in groups]
        for sid in groups:
            if sid not in ordered_sids:
                ordered_sids.append(sid)

        play_from, play_url = [], []
        for sid in ordered_sids:
            alias = tab_names.get(sid) or ("线路%s" % sid)
            play_from.append(alias)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in groups[sid]))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_remarks": remarks or ("%d条线路" % len(groups)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # -------- 播放 --------
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
                    aa = json.loads(m.group(1))
                    if int(aa.get("encrypt", 0) or 0) == 0:
                        m3u8 = aa.get("url", "") or ""
                    if m3u8:
                        m3u8 = m3u8.replace("\\/", "/")
                except Exception as e:
                    self.log("  player_aaaa 解析失败: %s" % e)

        if m3u8:
            self.log("  => m3u8: %s" % m3u8[:160])
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
