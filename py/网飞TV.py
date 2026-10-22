# coding=utf-8
"""
网飞TV wangfei.tv | TVBox Python 爬虫 (V7.1 终极稳定版)
关键:
  - 修复了分类页（categoryContent）路由 404 导致“这里什么都没有”的问题
  - 引入了万能正则抓取（兼容首页、分类页、搜索页）
  - 保留了隐藏的 m3u8 直链 + 外挂线路解析
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
                self._session.mount('https://', _rq.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0))
            return self._session
        def fetch(self, url, headers=None, **kw):
            return self._sess.get(url, headers=headers, timeout=kw.get('timeout', 15))
        def log(self, *a, **kw):
            print("[wangfei]", *a)

    Spider = _BaseSpider

HOST = "https://www.wangfei.tv"
UA = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36")
DEFAULT_PIC = HOST + "/mxtheme/images/logo.png"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "5",  "type_name": "纪录片"},
    {"type_id": "47", "type_name": "短剧"},
]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "分类", "value": [{"n": "全部", "v": ""}]},
        {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "中国", "v": "中国"}, {"n": "美国", "v": "美国"}]},
        {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]},
    ]

# ===================== 万能正则 =====================
_RE_CARD = re.compile(
    r'<a\b[^>]*href="([^"]*/voddetail/[^"]+\.html)"[^>]*>[\s\S]{0,2000}?'
    r'<img[^>]*?(?:alt|title)="([^"]*)"[^>]*?(?:data-original|data-src|src)="([^"]*)"',
    re.S | re.I)

_RE_JSON_LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S | re.I)
_RE_EXT_LINK = re.compile(r'<a[^>]*class="module-play-list-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_META_DESC = re.compile(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_META_PIC = re.compile(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']*)["\']', re.I)

class Spider(Spider):

    def getName(self):
        return "网飞TV"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.site_url = (self.extend.get("host") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC

    def _fetch(self, url, timeout=15):
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=timeout)
            return getattr(rsp, "text", "") or ""
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
        s = re.sub(r"<[^>]+>", "", s)
        return s.replace("&nbsp;", " ").replace("&amp;", "&").strip()

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html: return videos
        for href, alt, pic in _RE_CARD.findall(html):
            href = href.replace("&amp;", "&")
            if href in seen: continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(alt)[:100],
                "vod_pic": self._fix_url(pic) or self.default_pic,
            })
        return videos

    def _page_count(self, html):
        if not html: return 1
        pages = re.findall(r'page=(\d+)', html)
        return max(int(p) for p in pages) + 1 if pages else 1

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        # 分类页路由轰炸：只要是列表页，全试一遍
        urls = []
        if page == 1:
            urls = [
                f"{self.site_url}/vodshow/id/{tid}.html",
                f"{self.site_url}/vodtype/{tid}.html"
            ]
        else:
            urls = [
                f"{self.site_url}/vodshow/id/{tid}/page/{page}.html",
                f"{self.site_url}/vodshow/page/{page}/id/{tid}.html",
                f"{self.site_url}/vodtype/{tid}.html?page={page}"
            ]
        
        videos = []
        for url in urls:
            self.log("category try: %s" % url)
            html = self._fetch(url)
            videos = self._extract_videos(html)
            if videos:
                self.log(f"  -> 成功抓取 {len(videos)} 条")
                break
                
        return {
            "list": videos, "page": page, "pagecount": self._page_count(html) if videos else page,
            "limit": 24, "total": 999,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        urls = [
            f"{self.site_url}/vodsearch/wd/{keyword}.html" + (f"?page={page}" if page > 1 else ""),
            f"{self.site_url}/vod/search?wd={keyword}" + (f"&page={page}" if page > 1 else "")
        ]
        videos = []
        for url in urls:
            html = self._fetch(url)
            videos = self._extract_videos(html)
            if videos: break
            
        return {"list": videos, "page": page, "pagecount": self._page_count(html) if videos else page, "limit": 24, "total": 999}

    def detailContent(self, ids):
        if not ids: return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        html = self._fetch(url)
        if not html: return {"list": []}

        name = (re.search(_RE_H1, html).group(1) if re.search(_RE_H1, html) else vod_id)
        pic = (re.search(_RE_META_PIC, html).group(1) if re.search(_RE_META_PIC, html) else self.default_pic)
        content = (re.search(_RE_META_DESC, html).group(1) if re.search(_RE_META_DESC, html) else "")

        lines = []
        # 抓隐藏直链
        for j_str in _RE_JSON_LD.findall(html):
            try:
                j_data = json.loads(j_str)
                if isinstance(j_data, dict) and j_data.get("@type") == "VideoObject":
                    c_url = j_data.get("contentUrl")
                    if c_url and ".m3u8" in c_url:
                        lines.append(("极速线路", "第1集$" + c_url))
                        break
            except: pass
            
        # 抓外挂线路
        eps = []
        for href, txt in _RE_EXT_LINK.findall(html):
            href = self._fix_url(href)
            if "xyz" in href and "voddetail" in href:
                eps.append(f"{self._clean(txt)}${href}")
        if eps: lines.append(("外挂聚合", "#".join(eps)))

        return {"list": [{
            "vod_id": vod_id, "vod_name": self._clean(name), "vod_pic": self._fix_url(pic), "vod_content": content,
            "vod_remarks": "共%d条线路" % len(lines),
            "vod_play_from": "$$$".join(x[0] for x in lines),
            "vod_play_url": "$$$".join(x[1] for x in lines),
        }]}

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        
        if ".m3u8" in play_page.lower() or ("xyz" in play_page and "voddetail" in play_page):
            return {"parse": 0 if ".m3u8" in play_page else 1, "playUrl": "", "url": play_page, "header": {"User-Agent": UA}}

        html = self._fetch(play_page)
        if not html: return {"parse": 1, "playUrl": "", "url": play_page, "header": {"User-Agent": UA}}

        m = re.search(r"player_aaaa\s*=\s*({.*?})\s*;", html, re.S)
        if m:
            try:
                cfg = json.loads(m.group(1))
                play_url = cfg.get("url", "")
                if play_url:
                    play_url = self._fix_url(play_url)
                    return {"parse": 0 if ".m3u8" in play_url.lower() else 1, "playUrl": "", "url": play_url, "header": {"User-Agent": UA, "Referer": play_page}}
            except: pass

        m = re.search(r'<iframe\b[^>]*src=["\']([^"\']+)["\']', html, re.I)
        if m: return {"parse": 1, "playUrl": "", "url": self._fix_url(m.group(1)), "header": {"User-Agent": UA, "Referer": play_page}}

        return {"parse": 1, "playUrl": "", "url": play_page, "header": {"User-Agent": UA}}

    def isVideoFormat(self, url): return ".m3u8" in url or ".mp4" in url
    def manualVideoCheck(self): return False
    def destroy(self): pass
    def close(self): self.destroy()
