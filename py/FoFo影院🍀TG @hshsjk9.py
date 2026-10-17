# coding=utf-8
"""
FoFo影院 fofo22.com | TVBox Python 爬虫 
关键:
  - 多级正则兜底解析列表
  - 解密 var urlList 播放数据
  - POST /source/ 获取 m3u8
"""
import re
import sys
import json
import ast
import time
import urllib.parse
import urllib.request

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
DEFAULT_PIC = "https://pic.rmb.bdstatic.com/bjh/user/default.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "dianying",  "type_name": "电影"},
    {"type_id": "dianshiju", "type_name": "电视剧"},
    {"type_id": "zongyi",    "type_name": "综艺"},
    {"type_id": "dongman",   "type_name": "动漫"},
]

_SORTS = [{"n": "按时间", "v": "0"},
          {"n": "按人气", "v": "1"},
          {"n": "按评分", "v": "2"}]

_YEARS = [{"n": "全部", "v": "0"}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2004, -1)] + \
         [{"n": "其他", "v": "1"}]

_AREAS = [
    {"n": "全部", "v": "0"}, {"n": "中国大陆", "v": "1"}, {"n": "美国", "v": "2"},
    {"n": "香港", "v": "3"}, {"n": "台湾", "v": "4"}, {"n": "日本", "v": "5"},
    {"n": "韩国", "v": "6"}, {"n": "英国", "v": "7"}, {"n": "法国", "v": "8"},
    {"n": "德国", "v": "9"}, {"n": "意大利", "v": "10"}, {"n": "西班牙", "v": "11"},
    {"n": "印度", "v": "12"}, {"n": "泰国", "v": "13"}, {"n": "俄罗斯", "v": "14"},
    {"n": "伊朗", "v": "15"}, {"n": "加拿大", "v": "16"}, {"n": "澳大利亚", "v": "17"},
    {"n": "爱尔兰", "v": "18"}, {"n": "瑞典", "v": "19"}, {"n": "巴西", "v": "20"},
    {"n": "丹麦", "v": "21"},
]

_FILTERS_MAP = {
    "dianying":  ["全部", "剧情", "喜剧", "动作", "爱情", "科幻", "悬疑", "惊悚",
                  "恐怖", "犯罪", "同性", "音乐", "歌舞", "传记", "历史", "战争",
                  "西部", "奇幻", "冒险", "灾难", "武侠", "伦理"],
    "dianshiju": ["全部", "剧情", "喜剧", "动作", "爱情", "科幻", "悬疑", "惊悚",
                  "恐怖", "犯罪", "同性", "音乐", "歌舞", "传记", "历史", "战争",
                  "西部", "奇幻", "冒险", "灾难", "武侠", "伦理"],
    "zongyi":    ["全部", "真人秀", "脱口秀", "纪录片", "传记", "歌舞"],
    "dongman":   ["全部", "剧情", "喜剧", "动作", "爱情", "科幻", "悬疑", "惊悚",
                  "恐怖", "犯罪", "同性", "音乐", "歌舞", "传记", "历史", "战争",
                  "西部", "奇幻", "冒险", "灾难", "武侠", "伦理"],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "genre", "name": "类型",
         "value": [{"n": x, "v": str(i) if x != "全部" else "0"}
                   for i, x in enumerate(_FILTERS_MAP.get(tid, ["全部"]))]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]

# 详情页提取
_RE_TITLE = re.compile(r'<h1[^>]*class="product-title"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_COVER = re.compile(r'<img[^>]*?src="([^"]*)"[^>]*?class="thumb"', re.I)
_RE_OG_IMAGE = re.compile(r'<meta[^>]*property="og:image"[^>]*content="([^"]*)"', re.I)
_RE_INTRO = re.compile(r'剧情简介：\s*<span>([\s\S]*?)</span>', re.I)
_RE_OG_DESC = re.compile(r'<meta[^>]*property="og:description"[^>]*content="([^"]*)"', re.I)
_RE_DIRECTOR = re.compile(r'导演：\s*<span>([\s\S]*?)</span>', re.I)
_RE_ACTOR = re.compile(r'主演：\s*<span>([\s\S]*?)</span>', re.I)
_RE_A_TAG = re.compile(r'<a[^>]*>([^<]*)</a>', re.I)
_RE_SCORE = re.compile(r'<span\s+class="rate">([\d.]+)</span>', re.I)

# 剧集加密数据
_RE_URLLIST = re.compile(r'var\s+urlList\s*=\s*decryptDict\((\{[\s\S]*?\})\)', re.S)


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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._warmed = False
        self.log("init: site=%s" % self.site_url)

    def _warm_up(self):
        if self._warmed:
            return
        try:
            self._fetch(self.site_url + "/", timeout=15)
            self._warmed = True
            self.log("预热完成")
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _fetch(self, url, timeout=60, headers=None, method='GET', data=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout, method=method, data=data)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            elif hasattr(rsp, "content"):
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

    # 【核心修复】完全使用你提供的精确正则提取
    def _extract_videos(self, html):
        videos = []
        if not html:
            self.log("  HTML 为空")
            return videos
            
        pattern = re.compile(
            r'<a\s+href="(/(?:dianying|dianshiju|zongyi|dongman)/(\d+))"[^>]*class="thumbnail"[^>]*>.*?'
            r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"[^>]*>.*?'
            r'<div\s+class="note"><span>([^<]*)</span>',
            re.DOTALL
        )
        seen = set()
        for href, vid, pic, name, note in pattern.findall(html):
            if vid in seen:
                continue
            seen.add(vid)
            vod_name = name.strip() if name.strip() else vid
            videos.append({
                "vod_id": href.lstrip('/'),
                "vod_name": vod_name,
                "vod_pic": self._fix_url(pic),
                "vod_remarks": note.strip()
            })
            
        self.log("  提取: %d 条" % len(videos))
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = re.findall(r'page=(\d+)', html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        return 1

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        self._warm_up()
        url = self.site_url + "/"
        html = self._fetch(url)
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        # 【核心修复】参数名必须是 genre
        genre = str(extend.get("genre", "0")).strip() or "0"
        area = str(extend.get("area", "0")).strip() or "0"
        year = str(extend.get("year", "0")).strip() or "0"
        sort = str(extend.get("sort", "0")).strip() or "0"

        # 第一页不加 ?page=1，其他照旧
        url = "%s/%s/%s-%s-%s-%s" % (self.site_url, tid, genre, area, year, sort)
        if page > 1:
            url += "?page=%d" % page

        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/search?q=%s&page=%d" % (self.site_url, keyword, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
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
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        name = ""
        try:
            m = _RE_TITLE.search(html)
            if m:
                name = re.sub(r'\s*<span[^>]*>.*?</span>', "", m.group(1), flags=re.S)
                name = self._clean(name)
        except Exception:
            pass
        if not name:
            try:
                m = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"', html, re.I)
                if m:
                    name = self._clean(m.group(1))
            except Exception:
                pass
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        pic = self.default_pic
        try:
            m = _RE_COVER.search(html)
            if m:
                pic = self._fix_url(m.group(1))
            else:
                m = _RE_OG_IMAGE.search(html)
                if m:
                    pic = self._fix_url(m.group(1))
        except Exception:
            pass

        content = ""
        try:
            m = _RE_INTRO.search(html)
            if m:
                content = self._clean(m.group(1))
        except Exception:
            pass
        if not content:
            try:
                m = _RE_OG_DESC.search(html)
                if m:
                    content = self._clean(m.group(1))
            except Exception:
                pass

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        director = ""
        try:
            m = _RE_DIRECTOR.search(html)
            if m:
                director = ", ".join(self._clean(x) for x in _RE_A_TAG.findall(m.group(1)) if self._clean(x))
        except Exception:
            pass

        actor = ""
        try:
            m = _RE_ACTOR.search(html)
            if m:
                actor = ", ".join(self._clean(x) for x in _RE_A_TAG.findall(m.group(1)) if self._clean(x))
        except Exception:
            pass

        score = ""
        try:
            m = _RE_SCORE.search(html)
            if m:
                score = m.group(1)
        except Exception:
            pass

        sources = []
        url_list = []
        try:
            m = _RE_URLLIST.search(html)
            if m:
                raw = m.group(1)
                obj = ast.literal_eval(raw)
                dec = self._decrypt_val(obj)
                sources = dec.get("source", [])
                url_list = dec.get("url_list", [])
        except Exception as e:
            self.log("  剧集解析失败: %s" % e)

        self.log("  线路: %s" % sources)

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

        now = int(time.time())
        cache_key = "%s_%s" % (flag, sid)
        if cache_key in self._play_cache:
            ts, res = self._play_cache[cache_key]
            if now - ts < 600:
                return res

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
            res = {
                "parse": 0,
                "playUrl": "",
                "url": m3u8,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                    "Origin": self.site_url,
                },
            }
            self._play_cache[cache_key] = (now, res)
            return res

        self.log("  source 返回无效，走嗅探")
        res = {"parse": 1, "playUrl": "", "url": self.site_url + "/",
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[cache_key] = (now, res)
        return res

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
