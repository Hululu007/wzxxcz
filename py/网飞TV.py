# coding=utf-8
"""
网飞TV wangfei.tv | TVBox Python 爬虫 (V7.0 豆花风格重构版)
关键:
  - 解析详情页隐藏的 JSON-LD 结构获取最高清 m3u8 直链（极速线路）
  - 解析外挂的“线路1-线路9”聚合跳转链接
  - 兼容搜索页的 module-card-item 结构
  - 拦截并修复搜索/分类下页面空白的问题
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
                print("[wangfei]", *a)
            except Exception:
                pass

    Spider = _BaseSpider

HOST = "https://www.wangfei.tv"
UA = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36")
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
        {"key": "class", "name": "分类",
         "value": [{"n": "全部", "v": ""}]},
        {"key": "area", "name": "地区",
         "value": [{"n": "全部", "v": ""}, {"n": "中国", "v": "中国"}, {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"}]},
        {"key": "year", "name": "年份",
         "value": [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]},
    ]

# ===================== 正则 =====================
_RE_CARD = re.compile(
    r'<a\b[^>]*href="([^"]*/voddetail/[^"]+\.html)"[^>]*>[\s\S]{0,1500}?'
    r'<img[^>]*?(?:alt|title)="([^"]*)"[^>]*?(?:data-original|data-src|src)="([^"]*)"',
    re.S | re.I)

_RE_DETAIL_PATH = re.compile(r"/voddetail/[^\"'?#<>\s]+\.html", re.I)

# 详情页 JSON-LD (核心：找 m3u8 直链)
_RE_JSON_LD = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>',
    re.S | re.I)

# 详情页 外挂线路 (核心：找 xyz 外部跳转)
_RE_EXT_LINK = re.compile(
    r'<a[^>]*class="module-play-list-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.S | re.I)

_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_META_DESC = re.compile(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_META_PIC = re.compile(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']*)["\']', re.I)

# 播放页解析
_RE_PLAYER_AA = re.compile(r"player_aaaa\s*=\s*({.*?})\s*;", re.S)
_RE_IFRAME = re.compile(r'<iframe\b[^>]*src=["\']([^"\']+)["\']', re.I)

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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=15, headers=None):
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
        return s.strip()

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
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

        # 备用解析（针对搜索页 module-card-item）
        for m in re.finditer(r'<div[^>]*class="[^"]*module-card-item[^"]*"[^>]*>[\s\S]*?</div>', html, re.I):
            block = m.group(0)
            href_m = re.search(r'href="([^"]*/voddetail/[^"]+\.html)"', block, re.I)
            if not href_m: continue
            href = href_m.group(1)
            if href in seen: continue
            seen.add(href)
            
            title_m = re.search(r'<strong>([^<]+)</strong>', block, re.I)
            title = self._clean(title_m.group(1)) if title_m else ""
            
            pic_m = re.search(r'<img[^>]*src="([^"]+)"', block, re.I)
            pic = self._fix_url(pic_m.group(1)) if pic_m else self.default_pic
            
            videos.append({
                "vod_id":      href,
                "vod_name":    title,
                "vod_pic":     pic,
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
        videos = self._extract_videos(html)
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        if page == 1:
            url = "%s/vodshow/id/%s.html" % (self.site_url, tid)
        else:
            url = "%s/vodshow/page/%d/id/%s.html" % (self.site_url, page, tid)

        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/vodsearch/wd/%s.html" % (self.site_url, keyword)
        if page > 1:
            url = "%s?page=%d" % (url, page)
            
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
        try:
            m = _RE_H1.search(html)
            if m:
                name = self._clean(m.group(1))
        except Exception:
            pass
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        try:
            m = _RE_META_PIC.search(html)
            if m:
                pic = self._fix_url(m.group(1))
        except Exception:
            pass

        # 简介
        content = ""
        try:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        except Exception:
            pass

        # ========= 核心：提取极速线路 (JSON-LD) =========
        lines = []
        json_lds = _RE_JSON_LD.findall(html)
        for j_str in json_lds:
            try:
                j_data = json.loads(j_str)
                if isinstance(j_data, dict) and j_data.get("@type") == "VideoObject":
                    content_url = j_data.get("contentUrl")
                    if content_url and ".m3u8" in content_url:
                        self.log("  发现隐藏极速M3U8: %s" % content_url[:80])
                        lines.append(("极速线路", "第1集$" + content_url))
                        break
            except Exception:
                pass

        # ========= 核心：提取外挂线路 (线路1-9) =========
        ext_links = _RE_EXT_LINK.findall(html)
        eps = []
        for href, txt in ext_links:
            txt = self._clean(txt)
            href = self._fix_url(href)
            if "xyz" in href and "voddetail" in href:
                eps.append("%s$%s" % (txt, href))
        
        if eps:
            self.log("  发现外挂线路: %d 条" % len(eps))
            lines.append(("外挂聚合", "#".join(eps)))

        if not lines:
            self.log("❌ 未发现可播放线路")

        play_from = []
        play_url = []
        for label, urls in lines:
            play_from.append(label)
            play_url.append(urls)

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_remarks": "共%d条线路" % len(lines),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # -------- 播放 --------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        
        # 如果是 m3u8 直链（极速线路被直接点击）
        if ".m3u8" in play_page.lower():
            self.log("=> 直链 m3u8: %s" % play_page[:80])
            return {
                "parse": 0,
                "playUrl": "",
                "url": play_page,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
            
        # 如果是外部聚合站（外挂聚合被点击）
        if "xyz" in play_page and "voddetail" in play_page:
            self.log("=> 外部聚合站跳转: %s" % play_page[:80])
            return {
                "parse": 1,
                "playUrl": "",
                "url": play_page,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }

        # 兜底逻辑 (用于解析常规播放页)
        self.log("player: %s" % play_page)
        html = self._fetch(play_page)
        
        if not html:
            return {"parse": 1, "playUrl": "", "url": play_page, "header": {"User-Agent": UA}}

        # 匹配 player_aaaa 配置
        m = _RE_PLAYER_AA.search(html)
        if m:
            try:
                cfg = json.loads(m.group(1))
                play_url = cfg.get("url", "")
                if play_url:
                    if play_url.startswith("/"):
                        play_url = self.site_url + play_url
                    elif play_url.startswith("//"):
                        play_url = "https:" + play_url
                    
                    if ".m3u8" in play_url.lower():
                        return {
                            "parse": 0,
                            "playUrl": "",
                            "url": play_url,
                            "header": {"User-Agent": UA, "Referer": play_page},
                        }
                    else:
                        return {
                            "parse": 1,
                            "playUrl": "",
                            "url": play_url,
                            "header": {"User-Agent": UA, "Referer": play_page},
                        }
            except Exception:
                pass

        # 匹配 iframe
        m = _RE_IFRAME.search(html)
        if m:
            iframe_url = self._fix_url(m.group(1))
            return {
                "parse": 1,
                "playUrl": "",
                "url": iframe_url,
                "header": {"User-Agent": UA, "Referer": play_page},
            }

        return {"parse": 1, "playUrl": "", "url": play_page, "header": {"User-Agent": UA}}

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
