# coding=utf-8
"""
蝶卡影视 diekawang.com TVBox爬虫
适配模板：FongMi / WebHtv Python Spider
首页、分类、搜索、详情、选集、播放解析
"""
import re
import sys
import json
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
            r = self._sess.get(url, headers=headers, timeout=timeout,** kw)
            r.encoding = 'utf-8'
            return r
        def log(self, *a, **kw):
            try:
                print("[diekawang]", *a)
            except Exception:
                pass
    Spider = _BaseSpider

HOST = "https://www.diekawang.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
DEFAULT_PIC = HOST + "/static/images/nopic.jpg"
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "vod/1/1", "type_name": "电影"},
    {"type_id": "vod/1/2", "type_name": "电视剧"},
    {"type_id": "vod/1/3", "type_name": "综艺"},
    {"type_id": "vod/1/4", "type_name": "动漫"},
    {"type_id": "vod/1/457", "type_name": "短剧"},
]
FILTERS = {}
for item in CLASSES:
    tid = item["type_id"]
    FILTERS[tid] = [
        {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}]},
        {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}]},
        {"key": "sort", "name": "排序", "value": [{"n": "最新", "v": "new"}, {"n": "热门", "v": "hot"}]},
    ]

# 正则表达式
RE_CARD = re.compile(r'<a href="([^"]+)"[^>]*>.*?<img.*?src="([^"]+)" alt="([^"]+)"', re.S | re.I)
RE_PLAY_URL = re.compile(r'var video = "([^"]+)";', re.S)
RE_TITLE = re.compile(r'<h1>(.*?)</h1>', re.S)
RE_DESC = re.compile(r'<div class="desc">(.*?)</div>', re.S)
RE_EP_ITEM = re.compile(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', re.S)

class Spider(Spider):
    def getName(self):
        return "蝶卡影视"

    def init(self, extend=""):
        self.extend = json.loads(extend) if extend else {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Referer": self.site_url + "/",
        }
        self._play_cache = {}

    def _fetch(self, url):
        try:
            resp = self.fetch(url, headers=self.headers, timeout=20)
            return resp.text
        except Exception as e:
            self.log("请求失败", url, e)
            return ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.site_url + url
        if not url.startswith("http"):
            return urllib.parse.urljoin(self.site_url, url)
        return url

    def _clean_html(self, text):
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text)
        text = text.replace("&nbsp;", " ").strip()
        return text

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/index.html")
        videos = []
        items = RE_CARD.findall(html)
        for href, pic, name in items:
            vid = self._fix_url(href)
            img = self._fix_url(pic)
            videos.append({
                "vod_id": vid,
                "vod_name": self._clean_html(name),
                "vod_pic": img,
                "vod_remarks": ""
            })
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        url = f"{self.site_url}/{tid}?page={page}"
        html = self._fetch(url)
        videos = []
        items = RE_CARD.findall(html)
        for href, pic, name in items:
            vid = self._fix_url(href)
            img = self._fix_url(pic)
            videos.append({
                "vod_id": vid,
                "vod_name": self._clean_html(name),
                "vod_pic": img,
                "vod_remarks": ""
            })
        return {
            "list": videos,
            "page": page,
            "pagecount": 100,
            "limit": 24
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg)
        kw = urllib.parse.quote(key)
        url = f"{self.site_url}/search/index.html?wd={kw}&page={page}"
        html = self._fetch(url)
        videos = []
        items = RE_CARD.findall(html)
        for href, pic, name in items:
            vid = self._fix_url(href)
            img = self._fix_url(pic)
            videos.append({
                "vod_id": vid,
                "vod_name": self._clean_html(name),
                "vod_pic": img,
                "vod_remarks": ""
            })
        return {
            "list": videos,
            "page": page,
            "pagecount": 100,
            "limit": 24
        }

    def detailContent(self, ids):
        vod_url = ids[0]
        html = self._fetch(vod_url)
        if not html:
            return {"list": []}

        # 标题
        title_match = RE_TITLE.search(html)
        vod_name = self._clean_html(title_match.group(1)) if title_match else ""

        # 简介
        desc_match = RE_DESC.search(html)
        vod_content = self._clean_html(desc_match.group(1)) if desc_match else ""
        vod_content = INTRO_PREFIX + "\n" + vod_content

        # 选集列表
        ep_list = []
        ep_items = RE_EP_ITEM.findall(html)
        for ep_href, ep_name in ep_items:
            ep_url = self._fix_url(ep_href)
            ep_list.append((self._clean_html(ep_name), ep_url))

        play_from = ["默认线路"]
        play_url = ["#".join([f"{name}${url}" for name, url in ep_list])]

        vod_info = {
            "vod_id": vod_url,
            "vod_name": vod_name,
            "vod_pic": DEFAULT_PIC,
            "vod_content": vod_content,
            "vod_actor": "",
            "vod_director": "",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url)
        }
        return {"list": [vod_info]}

    def playerContent(self, flag, id, vipFlags):
        play_html = self._fetch(id)
        m = RE_PLAY_URL.search(play_html)
        if m:
            source_b64 = m.group(1)
            try:
                real_url = base64.b64decode(source_b64).decode("utf-8")
                return {
                    "parse": 0,
                    "url": real_url,
                    "header": {
                        "User-Agent": UA,
                        "Referer": id
                    }
                }
            except Exception as e:
                self.log("base64解码失败", e)
        # 解码失败降级嗅探
        return {
            "parse": 1,
            "url": id,
            "header": {"User-Agent": UA, "Referer": id}
        }

    def localProxy(self, param):
        return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass
