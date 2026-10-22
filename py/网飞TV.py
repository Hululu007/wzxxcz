# coding=utf-8
"""
网飞TV wangfei.tv | TVBox Python 爬虫 (小橙子特供版)
关键:
  - 破解分类页假 ID 陷阱 (id=2 时自动暴力探测 22/31 等真实子类)
  - 从 JSON-LD 提取隐藏 m3u8 直链 (极速线路)
  - 抓取外部恶意跳转的聚合线路 (外挂聚合)
  - 简介前缀完整保留，风格 100% 对标豆花
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
                print("[wangfei]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.wangfei.tv"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
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
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=60, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            else:
                text = str(rsp)
            return text
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
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        matches = _RE_CARD.findall(html)
        self.log("  完整卡片: %d 条" % len(matches))

        if matches:
            for href, alt, pic in matches:
                href = href.replace("&amp;", "&")
                if href in seen:
                    continue
                seen.add(href)
                videos.append({
                    "vod_id":      href,
                    "vod_name":    self._clean(alt)[:100],
                    "vod_pic":     self._fix_url(pic) or self.default_pic,
                    "vod_remarks": "",
                })
            return videos

        # 纯文本兜底（搜索页等）
        for m in re.finditer(r'<a\b[^>]*href="([^"]*/voddetail/[^"]+\.html)"[^>]*>(.*?)</a>', html, re.S | re.I):
            href, txt = m.groups()
            href = href.replace("&amp;", "&")
            if href in seen: continue
            seen.add(href)
            txt = self._clean(txt)
            if txt.lower() in ("play", "detail", "more"): continue
            videos.append({
                "vod_id":      href,
                "vod_name":    txt[:100],
                "vod_pic":     self.default_pic,
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
        url = self.site_url + "/"
        html = self._fetch(url)
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        tid = str(tid)
        
        # 🚨 终极陷阱修补：电视剧大类 2 是空壳，暴力探测它的真实子类
        ids_to_try = [tid]
        if tid == "2": ids_to_try.extend(["22", "23", "24", "25", "28", "31"]) 
        elif tid == "1": ids_to_try.extend(["9", "10", "11", "12"])
        elif tid == "3": ids_to_try.extend(["31", "32", "34"])
        elif tid == "4": ids_to_try.extend(["38", "39", "40"])
        
        videos, html = [], ""
        for _id in ids_to_try:
            if page == 1:
                paths = [f"/vodshow/id/{_id}.html", f"/vodtype/{_id}.html"]
            else:
                paths = [
                    f"/vodshow/id/{_id}/page/{page}.html",
                    f"/vodshow/page/{page}/id/{_id}.html",
                ]
            
            for path in paths:
                url = self._fix_url(path)
                self.log("category try: %s" % url)
                html = self._fetch(url)
                videos = self._extract_videos(html)
                if videos:
                    self.log(f"  -> 成功抓取 {len(videos)} 条")
                    break
            if videos: break

        pagecount = self._page_count(html) if videos else page
        self.log("  最终: %d 条" % len(videos))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        paths = [
            f"/vodsearch/wd/{keyword}.html" + (f"?page={page}" if page > 1 else ""),
            f"/vod/search?wd={keyword}" + (f"&page={page}" if page > 1 else "")
        ]
        
        videos, html = [], ""
        for path in paths:
            url = self._fix_url(path)
            self.log("search: %s" % url)
            html = self._fetch(url)
            videos = self._extract_videos(html)
            if videos: break

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
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_META_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        # 简介（追加前缀）
        content = ""
        m = _RE_META_DESC.search(html)
        if m:
            content = self._clean(m.group(1))
            
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # 🚨 豆花风格强杀：隐藏直链 + 外挂线路
        groups = {}
        
        # 1. 提取 JSON-LD 直链
        for j_str in _RE_JSON_LD.findall(html):
            try:
                j_data = json.loads(j_str)
                if isinstance(j_data, dict) and j_data.get("@type") == "VideoObject":
                    c_url = j_data.get("contentUrl")
                    if c_url and ".m3u8" in c_url:
                        self.log("  发现极速M3U8: %s" % c_url[:80])
                        groups.setdefault("极速线路", []).append(("第1集", c_url))
                        break
            except Exception: pass

        # 2. 提取外挂聚合
        eps = []
        for m in _RE_EXT_LINK.finditer(html):
            href, txt = m.groups()
            href = self._fix_url(href)
            if "xyz" in href and "voddetail" in href:
                eps.append((self._clean(txt), href))
                
        if eps:
            self.log("  发现外挂线路: %d 条" % len(eps))
            groups.setdefault("外挂聚合", []).extend(eps)

        if not groups:
            self.log("❌ 详情页解析失败：未找到任何线路")
            return {"list": []}

        play_from = []
        play_url = []
        for origin, items in groups.items():
            play_from.append(origin)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in items))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_remarks": "%d条线路" % len(groups),
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

        # 极速直链直接放行
        if ".m3u8" in play_page.lower():
            res = {
                "parse": 0,
                "playUrl": "",
                "url": play_page,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
            self._play_cache[play_page] = (now, res)
            return res
            
        # 外挂站直接交给解析器去嗅探
        if "xyz" in play_page and "voddetail" in play_page:
            res = {
                "parse": 1,
                "playUrl": "",
                "url": play_page,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
            self._play_cache[play_page] = (now, res)
            return res

        # 常规兜底
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
                            res = {"parse": 0, "playUrl": "", "url": api_url, "header": {"User-Agent": UA, "Referer": play_page}}
                            self._play_cache[play_page] = (now, res)
                            return res
                except Exception:
                    pass

        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def localProxy(self, param):
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url", "")
            else:
                for pair in str(param).split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        if k == "url":
                            url = v
            if not url:
                return [200, "image/jpeg", b"", ""]
            url = urllib.parse.unquote(url) if "%" in url else url
            url = self._fix_url(url)
            rsp = self.fetch(url, headers={
                "User-Agent": UA, "Referer": self.site_url + "/"}, timeout=15)
            content = rsp.content
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
