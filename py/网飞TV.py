# coding=utf-8
"""
网飞TV wangfei.tv | TVBox Python 爬虫 (小橙子特供版 V9.0)
关键:
  - 破解分类页假 ID 陷阱 (自动探测 22/31 等真实子类)
  - 破解图片裂开陷阱 (强力补全缺失的 HTTP 协议和根路径)
  - 简介前缀保留
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
    import urllib3
    urllib3.disable_warnings()
    class _BaseSpider:
        def __init__(self):
            self._session = _rq.Session()
        def fetch(self, url, headers=None, **kw):
            return self._session.get(url, headers=headers, timeout=15)
        def log(self, *a): print("[wangfei]", *a)
    Spider = _BaseSpider

HOST = "https://www.wangfei.tv"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
DEFAULT_PIC = HOST + "/mxtheme/images/logo.png"
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

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
        {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "中国", "v": "中国"}]},
        {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]},
    ]

# ===================== 正则 =====================
# 优化了图片提取正则，兼容 data-original, data-src, src
_RE_CARD = re.compile(
    r'<a\b[^>]*href="([^"]*/voddetail/[^"]+\.html)"[^>]*>[\s\S]{0,2000}?'
    r'<img[^>]*?(?:alt|title)="([^"]*)"[^>]*?(?:data-original|data-src|data-lazy|data-echo|src)="([^"]*)"',
    re.S | re.I)

_RE_JSON_LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S | re.I)
_RE_EXT_LINK = re.compile(r'<a[^>]*class="module-play-list-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_META_DESC = re.compile(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_META_PIC = re.compile(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']*)["\']', re.I)

class Spider(Spider):
    def getName(self): return "网飞TV"

    def init(self, extend=""):
        try: self.extend = json.loads(extend) if extend else {}
        except Exception: self.extend = {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {"User-Agent": UA, "Referer": self.site_url + "/"}
        self._play_cache = {}

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
        # 补全 // 开头的链接
        if url.startswith("//"): return "https:" + url
        # 如果已经是完整链接，直接返回
        if url.startswith("http"): return url
        # 处理相对路径
        if url.startswith("/"): return self.site_url + url
        # 【关键修复】去掉多余的符号，强制拼接根路径
        url = url.lstrip('.')
        return urllib.parse.urljoin(self.site_url + "/", url)

    def _clean(self, s):
        if not s: return ""
        s = re.sub(r"<[^>]+>", "", s)
        return s.replace("&nbsp;", " ").replace("&amp;", "&").strip()

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html: return videos
        
        # 匹配视频卡片
        for href, alt, pic in _RE_CARD.findall(html):
            href = href.replace("&amp;", "&")
            if href in seen: continue
            seen.add(href)
            
            # 【图片修复】如果 pic 含有占位图关键字，尝试从网页的其他位置找图
            if "logo" in pic.lower() or not pic:
                pic = DEFAULT_PIC
                
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(alt)[:100],
                "vod_pic": self._fix_url(pic) or DEFAULT_PIC,
            })
        return videos

    def _page_count(self, html):
        if not html: return 1
        pages = re.findall(r'page=(\d+)', html)
        return max(int(p) for p in pages) + 1 if pages else 1

    def homeContent(self, filter=False): return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        tid = str(tid)
        
        # 【关键修复】电视剧大类 2 是空壳，我们直接去试子分类的真实 ID
        ids_to_try = [tid]
        if tid == "2": ids_to_try.extend(["22", "23", "31"]) 
        elif tid == "1": ids_to_try.extend(["9", "10", "11"])
        
        videos, html = [], ""
        for _id in ids_to_try:
            if page == 1:
                paths = [f"/vodshow/id/{_id}.html", f"/vodtype/{_id}.html"]
            else:
                paths = [f"/vodshow/id/{_id}/page/{page}.html", f"/vodshow/page/{page}/id/{_id}.html"]
            
            for path in paths:
                url = self._fix_url(path)
                self.log(f"category try: {url}")
                html = self._fetch(url)
                videos = self._extract_videos(html)
                if videos:
                    self.log(f"  -> 成功抓取 {len(videos)} 条")
                    break
            if videos: break

        return {
            "list": videos, "page": page, "pagecount": 999,
            "limit": 24, "total": 999,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        urls = [f"/vodsearch/wd/{keyword}.html", f"/vod/search?wd={keyword}"]
        videos, html = [], ""
        for path in urls:
            url = self._fix_url(path)
            html = self._fetch(url)
            videos = self._extract_videos(html)
            if videos: break
        return {"list": videos, "page": page, "pagecount": 999, "limit": 24, "total": 999}

    def detailContent(self, ids):
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        html = self._fetch(url)
        if not html: return {"list": []}

        name = ""
        m = _RE_H1.search(html)
        if m: name = self._clean(m.group(1))
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        pic = DEFAULT_PIC
        m = _RE_META_PIC.search(html)
        if m: pic = self._fix_url(m.group(1))

        content = ""
        m = _RE_META_DESC.search(html)
        if m: content = self._clean(m.group(1))
        content = INTRO_PREFIX + "\n" + content if content else INTRO_PREFIX

        # 提取线路
        groups = {}
        for j_str in _RE_JSON_LD.findall(html):
            try:
                j_data = json.loads(j_str)
                if isinstance(j_data, dict) and j_data.get("@type") == "VideoObject":
                    c_url = j_data.get("contentUrl")
                    if c_url and ".m3u8" in c_url:
                        groups.setdefault("极速线路", []).append(("第1集", c_url))
                        break
            except: pass

        eps = []
        for m in _RE_EXT_LINK.finditer(html):
            href, txt = m.groups()
            href = self._fix_url(href)
            if "xyz" in href and "voddetail" in href:
                eps.append((self._clean(txt), href))
        if eps: groups.setdefault("外挂聚合", []).extend(eps)

        play_from, play_url = [], []
        for origin, items in groups.items():
            play_from.append(origin)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in items))

        return {"list": [{
            "vod_id": vod_id, "vod_name": name, "vod_pic": pic, "vod_content": content,
            "vod_remarks": "共%d条" % len(groups),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        if ".m3u8" in play_page.lower() or "xyz" in play_page:
            return {"parse": 0 if ".m3u8" in play_page else 1, "url": play_page, "header": {"User-Agent": UA}}
        
        html = self._fetch(play_page)
        if html:
            m = re.search(r"player_aaaa\s*=\s*({.*?})\s*;", html, re.S)
            if m:
                try:
                    cfg = json.loads(m.group(1))
                    api_url = cfg.get("url", "")
                    if api_url:
                        api_url = self._fix_url(api_url)
                        if ".m3u8" in api_url.lower():
                            return {"parse": 0, "url": api_url, "header": {"User-Agent": UA, "Referer": play_page}}
                except: pass
        return {"parse": 1, "url": play_page, "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

    def localProxy(self, param): return [200, "text/plain", b"", ""]
    def isVideoFormat(self, url): return ".m3u8" in url or ".mp4" in url
    def manualVideoCheck(self): return False
    def destroy(self): pass
