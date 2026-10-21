# coding=utf-8
"""
水牛影院 sunnykings.com | TVBox Python 爬虫 (正则修复最终版)
关键:
  - 兼容首页及分类页的随机 Class 混淆
  - 修复分类列表数据因正则不匹配导致的空白
  - 直接提取 player_aaaa 直链 m3u8
  - 简介添加指定前缀
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
                print("[sunnykings]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://sunnykings.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/default18/template/mb13/statics/img/load.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "30", "type_name": "爽文短剧"},
    {"type_id": "36", "type_name": "伦理片"},
]

_DEFAULT_SUB_TID = {
    "1": "7", "2": "14", "3": "21", "4": "25", "30": "30", "36": "36"
}

_CLASS_ID_MAP = {
    "动作片": "7", "喜剧片": "8", "爱情片": "9", "科幻片": "10", 
    "恐怖片": "11", "剧情片": "12", "犯罪片": "29", "战争片": "13",
    "国产剧": "14", "港剧": "15", "台湾剧": "16", "韩剧": "17", 
    "日剧": "18", "泰剧": "31", "欧美剧": "19", "海外剧": "20",
    "大陆综艺": "21", "日韩综艺": "22", "港台综艺": "23", "欧美综艺": "24",
    "国产动漫": "25", "日本动漫": "26", "欧美动漫": "27", "海外动漫": "28",
    "爽文短剧": "30", "短剧": "30", "伦理片": "36"
}

_SORTS = [{"n": "按时间", "v": "time"},
          {"n": "按人气", "v": "hits"},
          {"n": "按评分", "v": "score"}]
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2005, -1)]
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
    {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"},
    {"n": "法国", "v": "法国"}, {"n": "英国", "v": "英国"},
    {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
    {"n": "德国", "v": "德国"}, {"n": "泰国", "v": "泰国"},
    {"n": "印度", "v": "印度"}, {"n": "意大利", "v": "意大利"},
    {"n": "西班牙", "v": "西班牙"}, {"n": "加拿大", "v": "加拿大"},
    {"n": "其他", "v": "其他"},
]
_LANGS = [
    {"n": "全部", "v": ""},
    {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"},
    {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"},
    {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"},
    {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"},
    {"n": "其它", "v": "其它"},
]

_FILTERS_MAP = {
    "1":  ["全部", "动作片", "喜剧片", "爱情片", "科幻片", "恐怖片", "剧情片", "犯罪片", "战争片"],
    "2":  ["全部", "国产剧", "港剧", "台湾剧", "韩剧", "日剧", "泰剧", "欧美剧", "海外剧"],
    "3":  ["全部", "大陆综艺", "日韩综艺", "港台综艺", "欧美综艺"],
    "4":  ["全部", "国产动漫", "日本动漫", "欧美动漫", "海外动漫"],
    "30": ["全部", "爽文短剧", "短剧"],
    "36": ["全部", "伦理片"],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "分类",
         "value": [{"n": x, "v": "" if x == "全部" else x} for x in _FILTERS_MAP.get(tid, ["全部"])]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "lang", "name": "语言", "value": _LANGS},
        {"key": "sort_field", "name": "排序", "value": _SORTS},
    ]


# ===================== 正则 =====================
# 兼容全随机 class，直接抓 href 和 title，不限制属性顺序
_RE_CARD = re.compile(r'<a[^>]+href="(/(?:news|weihu|wap|m)/\d+\.html)"[^>]+title="([^"]*)"', re.S | re.I)
_RE_CARD_IMG = re.compile(r'<a[^>]+href="(/(?:news|weihu|wap|m)/\d+\.html)"[^>]*(?:data-original|src)="([^"]*)"', re.S | re.I)

_RE_H1 = re.compile(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_H1_ANY = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)

# 简介
_RE_INTRO_FULL = re.compile(r'<span[^>]*class="[^"]*detail-content[^"]*"[^>]*>([\s\S]*?)</span>', re.I)
_RE_INTRO_SKETCH = re.compile(r'<span[^>]*class="[^"]*detail-sketch[^"]*"[^>]*>([\s\S]*?)</span>', re.I)
_RE_META_DESC = re.compile(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)

# 元信息
_RE_ACTOR_BLOCK = re.compile(r'<span[^>]*>\s*主演\s*[：:]\s*</span>([\s\S]*?)</p>', re.I)
_RE_DIRECTOR_BLOCK = re.compile(r'<span[^>]*>\s*导演\s*[：:]\s*</span>([\s\S]*?)</p>', re.I)
_RE_A_TEXT = re.compile(r'<a[^>]*>([^<]*)</a>', re.I)

_RE_SCORE = re.compile(r'<span[^>]*class="[^"]*branch[^"]*"[^>]*>\s*([\d.]+)\s*<', re.I)

_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.S)

_RE_LINE_BLOCK = re.compile(
    r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>\s*([^<]+?)\s*</h3>'
    r'[\s\S]*?<ul[^>]*class="[^"]*stui-content__playlist[^"]*"[^>]*>([\s\S]*?)</ul>',
    re.I)
_RE_EP_A = re.compile(r'<a[^>]+href="([^"]*?/tvplay/[^"]+?\.html)"[^>]*>([^<]*)</a>', re.I)

_LINE_ALIAS = {
    "1080zyk": "1080资源", "虎牙m3u8": "虎牙M3U8", "dyttm3u8": "电影天堂",
    "snm3u8": "snmM3U8", "暴风资源": "暴风资源",
}


class Spider(Spider):

    def getName(self):
        return "水牛影院"

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
        self._last_req_ts = 0.0
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=20, headers=None, retry=2):
        now = time.time()
        gap = now - self._last_req_ts
        if gap < 0.6:
            time.sleep(0.6 - gap)
        self._last_req_ts = time.time()

        h = dict(self.headers)
        if headers:
            h.update(headers)
        for attempt in range(retry + 1):
            try:
                rsp = self.fetch(url, headers=h, timeout=timeout)
                text = ""
                if hasattr(rsp, "text"):
                    text = rsp.text or ""
                elif hasattr(rsp, "content"):
                    text = rsp.content.decode("utf-8", "ignore")
                else:
                    text = str(rsp)

                if "请不要频繁操作" in text:
                    self.log("触发频率限制, 等待 3s 重试")
                    time.sleep(3.0)
                    continue
                return text
            except Exception as e:
                self.log("fetch FAIL(%d) %s -> %s" % (attempt, url, e))
                time.sleep(1.0)
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
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
              .replace("&ldquo;", "“").replace("&rdquo;", "”"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        # 1. 抓取有 title 的链接
        matches = _RE_CARD.findall(html)
        self.log("  正则匹配到: %d 条" % len(matches))
        
        if matches:
            for href, title in matches:
                href = href.replace("&amp;", "&")
                if href in seen:
                    continue
                seen.add(href)
                videos.append({
                    "vod_id":      href,
                    "vod_name":    self._clean(title)[:100],
                    "vod_pic":     self.default_pic,
                    "vod_remarks": "",
                })
            return videos

        # 2. 如果没抓到 title，退而求其次只抓 href
        matches_img = _RE_CARD_IMG.findall(html)
        self.log("  图片卡匹配到: %d 条" % len(matches_img))
        for href, pic in matches_img:
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    "未命名",
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html, page):
        if not html:
            return page
        m = re.search(r'href="[^"]*?/so-show/[^"]*?-(\d+)---', html)
        if m:
            try:
                return max(int(m.group(1)), page)
            except Exception:
                pass
        m = re.search(r'<span[^>]*class="[^"]*num[^"]*"[^>]*>\s*\d+\s*/\s*(\d+)\s*<', html)
        if m:
            try:
                return max(int(m.group(1)), page)
            except Exception:
                pass
        return page

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._extract_videos(html)}

    def _build_show_url(self, tid, extend, page):
        cls = extend.get("class", "")
        if cls:
            real_tid = _CLASS_ID_MAP.get(cls, tid)
        else:
            real_tid = _DEFAULT_SUB_TID.get(tid, tid)

        area = extend.get("area") or ""
        lang = extend.get("lang") or ""
        sort = extend.get("sort_field") or "time"
        year = extend.get("year") or ""
        
        # 强制年份，否则网站返回空
        if not year:
            year = "2025"

        parts = [real_tid]
        if area:
            parts.append("-%s" % urllib.parse.quote(area))
        else:
            parts.append("-")
        # class 占位
        parts.append("-")
        if lang:
            parts.append("-%s" % urllib.parse.quote(lang))
        else:
            parts.append("-")
        # letter 占位
        parts.append("-")
        parts.append("-%s" % sort)
        parts.append("-%d" % (page - 1))
        head = "".join(parts)

        url = "%s/so-show/%s---%s.html" % (self.site_url, head, year)
        return url

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}
        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        url = self._build_show_url(tid, extend, page)
        self.log("category: %s" % url)
        html = self._fetch(url)

        videos = self._extract_videos(html)
        pagecount = self._page_count(html, page)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))
        
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 30, "total": pagecount * 30,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        url = "%s/search/%s-------------.html" % (self.site_url, kw)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html, page),
            "limit": 30, "total": 999,
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

        name = ""
        try:
            m = _RE_H1.search(html) or _RE_H1_ANY.search(html)
            if m:
                name = self._clean(m.group(1))
        except Exception:
            pass
        if not name:
            try:
                m = re.search(r"<title>(.*?)</title>", html, re.S)
                if m:
                    name = self._clean(m.group(1).split("_")[0].split("-")[0])
            except Exception:
                pass
        name = name or vod_id

        pic = self.default_pic
        m = re.search(r'data-original="(/upload/vod/[^"]+)"', html)
        if m:
            pic = self._fix_url(m.group(1))
        else:
            m = re.search(r'<img[^>]+src="(/upload/vod/[^"]+)"', html)
            if m:
                pic = self._fix_url(m.group(1))

        content = ""
        try:
            m = _RE_INTRO_FULL.search(html) or _RE_INTRO_SKETCH.search(html)
            if m:
                content = self._clean(m.group(1))
        except Exception:
            pass
        if not content:
            try:
                m = _RE_META_DESC.search(html)
                if m:
                    content = self._clean(m.group(1))
            except Exception:
                pass
        content = INTRO_PREFIX + "\n" + content if content else INTRO_PREFIX

        actor = ""
        try:
            m = _RE_ACTOR_BLOCK.search(html)
            if m:
                names = [self._clean(x) for x in _RE_A_TEXT.findall(m.group(1))]
                actor = ", ".join([n for n in names if n])
        except Exception:
            pass

        director = ""
        try:
            m = _RE_DIRECTOR_BLOCK.search(html)
            if m:
                names = [self._clean(x) for x in _RE_A_TEXT.findall(m.group(1))]
                director = ", ".join([n for n in names if n])
        except Exception:
            pass

        score = ""
        try:
            m = _RE_SCORE.search(html)
            if m:
                score = m.group(1)
        except Exception:
            pass

        play_from = []
        play_url = []
        try:
            for m in _RE_LINE_BLOCK.finditer(html):
                line_name = self._clean(m.group(1))
                block = m.group(2)
                eps = _RE_EP_A.findall(block)
                if not eps:
                    continue
                alias = _LINE_ALIAS.get(line_name, line_name) or line_name
                items = []
                for href, ep_name in eps:
                    href = href.replace("&amp;", "&")
                    href = self._fix_url(href)
                    ep = self._clean(ep_name) or "正片"
                    items.append("%s$%s" % (ep, href))
                if items:
                    play_from.append(alias)
                    play_url.append("#".join(items))
        except Exception as e:
            self.log("  剧集解析失败: %s" % e)

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
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        url = ""
        if html:
            try:
                m = _RE_PLAYER.search(html)
                if m:
                    raw = m.group(1)
                    cfg = json.loads(raw)
                    url = cfg.get("url", "") or ""
            except Exception as e:
                self.log("player json 解析失败: %s" % e)
                m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if m2:
                    url = m2.group(1).replace("\\/", "/")

        if url:
            url = url.replace("\\/", "/")
            if url.startswith("//"):
                url = "https:" + url
            res = {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
            self._play_cache[play_page] = (now, res)
            self.log("  => m3u8: %s" % url[:160])
            return res

        # 兜底：交给 TVBox 嗅探
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
