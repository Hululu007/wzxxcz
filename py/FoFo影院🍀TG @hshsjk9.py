# coding=utf-8
"""
FoFo影院 fofo22.com | TVBox Python 爬虫
网站结构：
  - 分类页: /{tid}/{class}-{area}-{year}-{sort}?page={pg}
  - 搜索: /search?q={keyword}
  - 详情页: 剧集数据在 var urlList = decryptDict({...}) 中，加密规则为每个字符 charCode 减 1
  - 播放: POST /source/  data={"id": sid} 返回真实 m3u8 地址
"""
import re
import sys
import json
import ast
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
            method = kw.pop('method', 'GET').upper()
            data = kw.pop('data', None)
            if method == 'POST':
                r = self._sess.post(url, headers=headers, timeout=timeout, data=data, **kw)
            else:
                r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[fofo]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://fofo22.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "dianying",  "type_name": "电影"},
    {"type_id": "dianshiju", "type_name": "电视剧"},
    {"type_id": "zongyi",    "type_name": "综艺"},
    {"type_id": "dongman",   "type_name": "动漫"},
]

_CLASS_MAP = {
    "dianying":  [("全部", "0"), ("剧情", "1"), ("喜剧", "2"), ("动作", "3"),
                  ("爱情", "4"), ("科幻", "5"), ("悬疑", "6"), ("惊悚", "7"),
                  ("恐怖", "8"), ("犯罪", "9"), ("同性", "10"), ("音乐", "11"),
                  ("歌舞", "12"), ("传记", "13"), ("历史", "14"), ("战争", "15"),
                  ("西部", "16"), ("奇幻", "17"), ("冒险", "18"), ("灾难", "19"),
                  ("武侠", "20"), ("伦理", "21")],
    "dianshiju": [("全部", "0"), ("剧情", "1"), ("喜剧", "2"), ("动作", "3"),
                  ("爱情", "4"), ("科幻", "5"), ("悬疑", "6"), ("惊悚", "7"),
                  ("恐怖", "8"), ("犯罪", "9"), ("同性", "10"), ("音乐", "11"),
                  ("歌舞", "12"), ("传记", "13"), ("历史", "14"), ("战争", "15"),
                  ("西部", "16"), ("奇幻", "17"), ("冒险", "18"), ("灾难", "19"),
                  ("武侠", "20"), ("伦理", "21")],
    "zongyi":    [("全部", "0"), ("真人秀", "1"), ("脱口秀", "2"), ("纪录片", "3"),
                  ("传记", "4"), ("歌舞", "5")],
    "dongman":   [("全部", "0"), ("剧情", "1"), ("喜剧", "2"), ("动作", "3"),
                  ("爱情", "4"), ("科幻", "5"), ("悬疑", "6"), ("惊悚", "7"),
                  ("恐怖", "8"), ("犯罪", "9"), ("同性", "10"), ("音乐", "11"),
                  ("歌舞", "12"), ("传记", "13"), ("历史", "14"), ("战争", "15"),
                  ("西部", "16"), ("奇幻", "17"), ("冒险", "18"), ("灾难", "19"),
                  ("武侠", "20"), ("伦理", "21")],
}

_AREA_MAP = {
    "dianying":  [("全部", "0"), ("中国大陆", "1"), ("美国", "2"), ("香港", "3"),
                  ("台湾", "4"), ("日本", "5"), ("韩国", "6"), ("英国", "7"),
                  ("法国", "8"), ("德国", "9"), ("意大利", "10"), ("西班牙", "11"),
                  ("印度", "12"), ("泰国", "13"), ("俄罗斯", "14"), ("伊朗", "15"),
                  ("加拿大", "16"), ("澳大利亚", "17"), ("爱尔兰", "18"),
                  ("瑞典", "19"), ("巴西", "20"), ("丹麦", "21")],
    "dianshiju": [("全部", "0"), ("中国大陆", "1"), ("美国", "2"), ("香港", "3"),
                  ("台湾", "4"), ("日本", "5"), ("韩国", "6"), ("英国", "7"),
                  ("法国", "8"), ("德国", "9"), ("意大利", "10"), ("西班牙", "11"),
                  ("印度", "12"), ("泰国", "13"), ("俄罗斯", "14"), ("伊朗", "15"),
                  ("加拿大", "16"), ("澳大利亚", "17"), ("爱尔兰", "18"),
                  ("瑞典", "19"), ("巴西", "20"), ("丹麦", "21")],
    "zongyi":    [("全部", "0"), ("中国大陆", "1"), ("美国", "2"), ("香港", "3"),
                  ("台湾", "4"), ("日本", "5"), ("韩国", "6")],
    "dongman":   [("全部", "0"), ("中国大陆", "1"), ("美国", "2"), ("日本", "3"),
                  ("韩国", "4")],
}

_YEARS = [("全部", "0")] + [(str(y), str(y)) for y in range(2026, 2004, -1)] + [("其他", "1")]
_SORTS = [("按时间排序", "0"), ("按人气排序", "1"), ("按评分排序", "2")]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "分类",
         "value": [{"n": n, "v": v} for n, v in _CLASS_MAP.get(tid, [("全部", "0")])]},
        {"key": "area", "name": "地区",
         "value": [{"n": n, "v": v} for n, v in _AREA_MAP.get(tid, [("全部", "0")])]},
        {"key": "year", "name": "年代",
         "value": [{"n": n, "v": v} for n, v in _YEARS]},
        {"key": "sort", "name": "排序",
         "value": [{"n": n, "v": v} for n, v in _SORTS]},
    ]

_RE_CARD = re.compile(
    r'<a\s+[^>]*?href="/((?:dianying|dianshiju|zongyi|dongman)/\d+)"[^>]*?class="thumbnail"[^>]*>\s*'
    r'<img[^>]*?src="([^"]*)"[^>]*?alt="([^"]*)"',
    re.S | re.I)

_RE_TITLE = re.compile(r'<h[12][^>]*class="product-title"[^>]*>([\s\S]*?)</h[12]>', re.I)
_RE_COVER = re.compile(r'<img[^>]*?src="([^"]*)"[^>]*?class="thumb"', re.I)
_RE_OG_IMAGE = re.compile(r'<meta[^>]*property="og:image"[^>]*content="([^"]*)"', re.I)
_RE_DIRECTOR = re.compile(r'导演：\s*<span>([\s\S]*?)</span>', re.I)
_RE_ACTOR = re.compile(r'主演：\s*<span>([\s\S]*?)</span>', re.I)
_RE_A_TAG = re.compile(r'<a[^>]*>([^<]*)</a>', re.I)
_RE_INTRO = re.compile(r'剧情简介：\s*<span>([\s\S]*?)</span>', re.I)
_RE_OG_DESC = re.compile(r'<meta[^>]*property="og:description"[^>]*content="([^"]*)"', re.I)
_RE_SCORE = re.compile(r'<span\s+class="rate">([\d.]+)</span>', re.I)
_RE_URLLIST = re.compile(r'var\s+urlList\s*=\s*decryptDict\((\{[\s\S]*?\})\)\s*\$\(document\)', re.S)
_RE_LAST_PAGE = re.compile(r'尾页.*?page=(\d+)', re.S)


class Spider(Spider):

    def getName(self):
        return "FoFo影院"

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
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=20, headers=None, method='GET', data=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout,
                             method=method, data=data)
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

    def _decrypt_val(self, v):
        if isinstance(v, str):
            t = ''.join(chr(ord(c) - 1) for c in v)
            try:
                return json.loads(t)
            except Exception:
                return t
        if isinstance(v, list):
            return [self._decrypt_val(x) for x in v]
        if isinstance(v, dict):
            return {self._decrypt_val(k): self._decrypt_val(val)
                    for k, val in v.items()}
        return v

    def _parse_url_list(self, html):
        m = _RE_URLLIST.search(html)
        if not m:
            self.log("  未找到 urlList")
            return [], []
        raw = m.group(1)
        try:
            obj = ast.literal_eval(raw)
        except Exception as e:
            self.log("  literal_eval 失败: %s" % e)
            return [], []
        dec = self._decrypt_val(obj)
        sources = dec.get("source", [])
        url_list = dec.get("url_list", [])
        self.log("  线路: %s" % sources)
        return sources, url_list

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        for m in _RE_CARD.finditer(html):
            path, pic, name = m.group(1), m.group(2), m.group(3)
            if path in seen:
                continue
            seen.add(path)
            videos.append({
                "vod_id":      "/" + path,
                "vod_name":    self._clean(name),
                "vod_pic":     self._fix_url(pic),
                "vod_remarks": "",
            })
        self.log("  提取到 %d 条" % len(videos))
        return videos

    def _page_count(self, html):
        m = _RE_LAST_PAGE.search(html)
        if m:
            try:
                return int(m.group(1))
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

        # 严格遵循源码结构，无参数时默认全为 0，且首页不带 page 参数
        cls = str(extend.get("class", "0"))
        area = str(extend.get("area", "0"))
        year = str(extend.get("year", "0"))
        sort = str(extend.get("sort", "0"))

        if page == 1:
            url = "%s/%s/%s-%s-%s-%s" % (self.site_url, tid, cls, area, year, sort)
        else:
            url = "%s/%s/%s-%s-%s-%s?page=%d" % (self.site_url, tid, cls, area, year, sort, page)

        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 20, "total": pagecount * 20,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/search?q=%s&page=%d" % (self.site_url, keyword, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 20, "total": 999,
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
        m = _RE_TITLE.search(html)
        if m:
            name = re.sub(r'\s*<span[^>]*>.*?</span>', "", m.group(1), flags=re.S)
            name = self._clean(name)
        if not name:
            m = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"', html, re.I)
            if m:
                name = self._clean(m.group(1))
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = ""
        m = _RE_COVER.search(html)
        if m:
            pic = self._fix_url(m.group(1))
        if not pic:
            m = _RE_OG_IMAGE.search(html)
            if m:
                pic = self._fix_url(m.group(1))

        # 简介
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_OG_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        content = INTRO_PREFIX + ("\n" + content if content else "")

        # 导演 / 主演
        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            director = ", ".join(self._clean(x) for x in _RE_A_TAG.findall(m.group(1)) if self._clean(x))
        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            actor = ", ".join(self._clean(x) for x in _RE_A_TAG.findall(m.group(1)) if self._clean(x))

        # 评分
        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        # 剧集
        sources, url_list = self._parse_url_list(html)
        if not sources or not url_list:
            return {"list": []}

        play_from = []
        play_url = []
        for i, src_name in enumerate(sources):
            if i >= len(url_list):
                break
            eps = url_list[i]
            if not eps:
                continue
            alias = self._clean(src_name) or ("线路%d" % (i + 1))
            play_from.append(alias)
            parts = []
            for ep in eps:
                title = ep.get("title", "")
                sid = ep.get("sid", "")
                if not title:
                    title = "第%s集" % ep.get("episode", "")
                parts.append("%s$%s" % (title, sid))
            play_url.append("#".join(parts))

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
            "vod_play_url":  "$$$".join(play_url),
        }]}

    def playerContent(self, flag, id, vipFlags):
        sid = str(id).strip()
        self.log("player: flag=%s sid=%s" % (flag, sid))
        if not sid:
            return {"parse": 1, "playUrl": "", "url": "",
                    "header": {"User-Agent": UA}}

        api = self.site_url + "/source/"
        headers = {
            "User-Agent": UA,
            "Referer": self.site_url + "/",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "*/*",
            "Origin": self.site_url,
        }
        m3u8 = ""
        try:
            rsp = self.fetch(api, headers=headers, timeout=20,
                             method='POST', data={"id": sid})
            if hasattr(rsp, "text"):
                m3u8 = (rsp.text or "").strip()
            elif hasattr(rsp, "content"):
                m3u8 = rsp.content.decode("utf-8", "ignore").strip()
        except Exception as e:
            self.log("source POST fail: %s" % e)

        if m3u8 and (".m3u8" in m3u8 or ".mp4" in m3u8):
            if m3u8.startswith("//"):
                m3u8 = "https:" + m3u8
            self.log("  => m3u8: %s" % m3u8[:160])
            return {
                "parse": 0,
                "playUrl": "",
                "url": m3u8,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                    "Origin": self.site_url,
                },
            }

        # 兜底：交给 TVBox 嗅探
        self.log("  source 返回无效，走嗅探")
        return {
            "parse": 1,
            "playUrl": "",
            "url": self.site_url + "/",
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }

    def localProxy(self, param):
        return [200, "text/plain", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
