# coding=utf-8
"""
网飞TV wangfei.tv | TVBox Python 爬虫 (小橙子最强装备版)
关键突破:
  - 强杀分类假ID与假页面 (内置动态探测探测子类)
  - 破解筛选(Filter)隐藏参数，重写筛选面板
  - 精准提取 JSON-LD 隐藏直链 (干掉外挂跳转)
  - 全量日志追踪 (豆花风格)
"""
import sys
import json
import time
import re
import urllib.parse
from urllib.parse import urljoin, urlparse

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
            self._session = _rq.Session()

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._session.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[wangfei]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.wangfei.tv"
# 稳定不挂的默认封面图
DEFAULT_PIC = "https://www.wangfei.tv/upload/vod/20251211-1/569089b2bfc36db5559b19b6db5e9d8c.jpg"
UA = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36")

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "5",  "type_name": "纪录片"},
    {"type_id": "47", "type_name": "短剧"},
]

# ============ 刷选 BOSS 强杀：强行重写面板参数 ============
_YEARS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_AREAS = [{"n": "全部", "v": ""}, {"n": "中国", "v": "中国"}, {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"}]
_SORTS = [{"n": "最新更新", "v": "time"}, {"n": "最多播放", "v": "hits"}, {"n": "豆瓣评分", "v": "score"}]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]

# 全局暴力正则，无视任何 class 名字，直接抓 a 标签和它附近的 img
_RE_CARD = re.compile(
    r'<a\b[^>]*href="([^"]*/voddetail/[^"]+\.html)"[^>]*>[\s\S]{0,2000}?'
    r'<img[^>]*?(?:alt|title)="([^"]*)"[^>]*?(?:data-original|data-src|src)="([^"]*)"',
    re.S | re.I)


class Spider(Spider):

    def getName(self):
        return "网飞TV"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
        }
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=15, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            self.log(f"请求: {url}")
            rsp = self.fetch(url, headers=h, timeout=timeout)
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            self.log(f"  -> 状态: {getattr(rsp, 'status_code', 'unknown')}, 长度: {len(text)}")
            return text
        except Exception as e:
            self.log(f"fetch FAIL -> {e}")
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
        return urljoin(self.site_url + "/", url)

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        return s.strip()

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        matches = _RE_CARD.findall(html)
        self.log("  完整卡片: %d 条" % len(matches))

        for href, alt, pic in matches:
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            
            pic_url = self._fix_url(pic)
            if not pic_url or not pic_url.startswith("http"):
                pic_url = DEFAULT_PIC

            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(alt)[:100],
                "vod_pic":     pic_url,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = re.findall(r'page=(\d+)', html)
        if pages:
            try:
                return max(int(p) for p in pages) + 1
            except Exception:
                pass
        return 9999

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        url = "%s/" % (self.site_url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        tid = str(tid)
        
        if isinstance(extend, str):
            try: extend = json.loads(extend)
            except Exception: extend = {}
        if not extend: extend = {}

        # 组装筛选参数
        year = extend.get("year", "")
        area = extend.get("area", "")
        sort = extend.get("sort", "time") # 默认按时间更新

        # 暴力破除分类陷阱，同时拼接筛选路径
        ids_to_try = [tid]
        if tid == "2": ids_to_try.extend(["22", "23", "31", "38"])
        elif tid == "1": ids_to_try.extend(["9", "10", "11"])
        
        videos, html = [], ""
        for _id in ids_to_try:
            # 构建真实的筛选请求路径
            # 格式往往类似：/vodshow/id/22/year/2026.html 或 /vodshow/id/22/area/中国.html
            path_parts = [f"id/{_id}"]
            if area: path_parts.append(f"area/{urllib.parse.quote(area)}")
            if year: path_parts.append(f"year/{year}")
            if sort: path_parts.append(f"by/{sort}")
            
            route = "/".join(path_parts)
            
            if page == 1:
                paths = [f"/vodshow/{route}.html", f"/vodshow/{route}/page/{page}.html"]
            else:
                paths = [f"/vodshow/{route}/page/{page}.html"]

            for path in paths:
                url = self._fix_url(path)
                html = self._fetch(url)
                videos = self._extract_videos(html)
                if videos:
                    self.log(f"  -> 筛选命中！成功抓取 {len(videos)} 条")
                    break
            if videos:
                break

        pagecount = self._page_count(html) if videos else page
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": 999,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        paths = [
            f"/vodsearch/wd/{keyword}.html",
            f"/vod/search?wd={keyword}"
        ]
        
        videos, html = [], ""
        for path in paths:
            url = self._fix_url(path)
            html = self._fetch(url)
            videos = self._extract_videos(html)
            if videos:
                break

        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html) if videos else page,
            "limit": 24, "total": 999,
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log(f"详情解析: {url}")

        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题、封面、简介
        name = ""
        m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.I)
        if m: name = self._clean(m.group(1))
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        pic = DEFAULT_PIC
        m = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']*)["\']', html, re.I)
        if m: pic = self._fix_url(m.group(1))

        content = ""
        m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.I)
        if m: content = self._clean(m.group(1))
        content = INTRO_PREFIX + "\n" + content if content else INTRO_PREFIX

        # ========== 播放线路 Boss 斩杀 ==========
        lines = []
        
        # 1. 强杀 JSON-LD 直链 (最高清，速度最快)
        for j_str in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            try:
                j_data = json.loads(j_str)
                if isinstance(j_data, dict) and j_data.get("@type") == "VideoObject":
                    c_url = j_data.get("contentUrl")
                    if c_url and ".m3u8" in c_url:
                        self.log(f"  [命中直链] {c_url[:50]}...")
                        lines.append(("极速直链", "正片$" + c_url))
                        break
            except Exception: pass
            
        # 2. 抓取外挂聚合 (备用)
        eps = []
        for m in re.finditer(r'<a[^>]*class="module-play-list-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
            href, txt = m.groups()
            href = self._fix_url(href)
            if "xyz" in href and "voddetail" in href:
                eps.append(f"{self._clean(txt)}${href}")
        if eps:
            self.log(f"  [命中外挂] {len(eps)} 条")
            lines.append(("外挂跳转", "#".join(eps)))

        if not lines:
            self.log("❌ 详情页解析失败：未找到任何线路")

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_remarks": "共%d条线路" % len(lines) if lines else "暂无线路",
            "vod_play_from": "$$$".join(x[0] for x in lines),
            "vod_play_url":  "$$$".join(x[1] for x in lines),
        }]}

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log(f"播放请求: {play_page}")
        
        if ".m3u8" in play_page.lower():
            self.log("  -> 判定为 m3u8 直链，交给播放器")
            return {"parse": 0, "playUrl": "", "url": play_page, "header": {"User-Agent": UA}}
            
        if "xyz" in play_page and "voddetail" in play_page:
            self.log("  -> 判定为外挂聚合，交给嗅探")
            return {"parse": 1, "playUrl": "", "url": play_page, "header": {"User-Agent": UA}}

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
                            self.log("  -> 找到 player_aaaa 直链")
                            return {"parse": 0, "playUrl": "", "url": api_url, "header": {"User-Agent": UA, "Referer": play_page}}
                except Exception: pass

        self.log("  -> 找不到直链，交给 TVBox 兜底嗅探")
        return {"parse": 1, "playUrl": "", "url": play_page, "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

    def localProxy(self, param): return [200, "image/jpeg", b"", ""]
    def isVideoFormat(self, url): return ".m3u8" in url or ".mp4" in url
    def manualVideoCheck(self): return False
    def destroy(self): pass
    def close(self): self.destroy()
