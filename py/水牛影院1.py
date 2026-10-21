# coding=utf-8
"""
火龙果影视 | TVBox Python 爬虫
自动生成于 Spider AutoGen — 请按需微调正则后再上线
生成状态: 列表已命中 / 详情已命中 / 播放页 direct-m3u8
"""
import re
import sys
import json
import time
import html as _html
import hashlib
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
            kw.pop('allow_redirects', None)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[spider]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = 'https://www.gljade.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
DEFAULT_PIC = HOST + '/favicon.ico'

INTRO_PREFIX = '🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！'

CLASSES = [
    {"type_id": 'wd', "type_name": '1 变形金刚'},
    {"type_id": ';', "type_name": '搜索'},
    {"type_id": '1', "type_name": '电影'},
    {"type_id": '6', "type_name": '动作片'},
    {"type_id": '7', "type_name": '喜剧片'},
    {"type_id": '8', "type_name": '爱情片'},
    {"type_id": '9', "type_name": '科幻片'},
    {"type_id": '10', "type_name": '剧情片'},
    {"type_id": '11', "type_name": '战争片'},
    {"type_id": '41', "type_name": '动画片'},
    {"type_id": '12', "type_name": '记录片'},
    {"type_id": '39', "type_name": '恐怖片'},
    {"type_id": '2', "type_name": '电视剧'},
    {"type_id": '13', "type_name": '国产剧'},
    {"type_id": '14', "type_name": '香港剧'},
    {"type_id": '15', "type_name": '韩国剧'},
    {"type_id": '16', "type_name": '欧美剧'},
    {"type_id": '22', "type_name": '台湾剧'},
    {"type_id": '21', "type_name": '日本剧'},
    {"type_id": '20', "type_name": '泰国剧'},
    {"type_id": '23', "type_name": '海外剧'},
    {"type_id": '3', "type_name": '综艺片'},
    {"type_id": '25', "type_name": '大陆综艺'},
    {"type_id": '26', "type_name": '日韩综艺'},
    {"type_id": '27', "type_name": '港台综艺'},
    {"type_id": '28', "type_name": '欧美综艺'},
    {"type_id": '4', "type_name": '动漫'},
    {"type_id": '29', "type_name": '国产动漫'},
    {"type_id": '30', "type_name": '日本动漫'},
    {"type_id": '42', "type_name": '港台动漫'},
]

_YEARS = [{"n": "全部", "v": ""}] + [{"n": y, "v": y} for y in ('2010', '2012', '2013', '2014', '2015', '2016', '2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026')]
_AREAS = [{"n": "全部", "v": ""}] + [{"n": a, "v": a} for a in ('中国大陆', '美国', '日本', '韩国', '中国香港', '中国台湾', '英国', '法国', '德国', '印度', '泰国')]
_SORTS = [{"n": "热度最高", "v": 'play_hot'}, {"n": "最新更新", "v": 'time'}]

FILTERS = {
    c["type_id"]: [
        {"key": "class", "name": "分类", "value": [{"n": "全部", "v": ""}]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort_field", "name": "排序", "value": _SORTS},
    ] for c in CLASSES
}


# ===================== 正则 =====================
# 列表卡片片段: <ul class="aui-nav-dow">
														<li><a href="/medialist/id/6.html" title="动作片">动作片</a></li>
											
_RE_CARD = re.compile(
    r'<a[^>]*?href="((?:/video/)[^"]*?\d[^"]*?(?:\.html|\?[^"]*))"([^>]*)>'
    r'([\s\S]{0,700}?)</a>',
    re.S | re.I)
_RE_HREF = re.compile(r'href="((?:/video/)[^"]*?\d[^"]*)', re.I)
_RE_PLAY_HREF = re.compile(r'/(?:tvplay|vodplay|play|v_play)/', re.I)
# 本站卡片: title/data-original 直接在 <a> 标签属性上
_RE_A_TITLE = re.compile(r'title="([^"]*)"', re.I)
_RE_A_PIC = re.compile(r'(?:data-original|data-src|data-lazy-src|src)="([^"]+)"', re.I)
_RE_IMG = re.compile(
    r'<img[^>]*?alt="([^"]*)"[^>]*?(?:data-src|src)="([^"]*)"',
    re.S | re.I)

_RE_EPISODE_A = re.compile(r'<a\s+href="([^"]+)"([^>]*?)>(.*?)</a>', re.S | re.I)
_RE_DATA_ORIGIN = re.compile(r'data-origin="([^"]+)"', re.I)
_RE_DATA_TITLE = re.compile(r'data-title="([^"]+)"', re.I)
_RE_EP_ORIGIN_URL = re.compile(r'/(?:tvplay|vodplay|play)/[^"\']*?-(\d+)-\d+\.html', re.I)

_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE_TAG = re.compile(r'<title[^>]*>([\s\S]*?)</title>', re.I)
_RE_OG_IMG = re.compile(r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)', re.I)
_RE_PIC = re.compile(r'(?:data-original|data-src)="([^"]+\.(?:jpg|png|webp|jpeg)[^"]*)"', re.I)
_RE_INTRO = re.compile(r'<span[^>]*>\s*简介\s*[:：]\s*</span>\s*([\s\S]*?)</div>', re.S | re.I)
_RE_META_DESC = re.compile(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_DIRECTOR = re.compile(r'导演\s*[:：]\s*([^\s\n主]{1,40})')
_PAGEBOX_RE = re.compile(
    r'<(?:ul|div|nav)[^>]*class=["\']?[^"\']*'
    r'(?:stui-page|pagination|page-nav|pagenav|pagebar|page-num|page-box)[^>]*>'
    r'(.*?)</(?:ul|div|nav)>', re.S | re.I)
_RE_ACTOR = re.compile(r'主演\s*[:：]\s*([^\n]{1,100})')
_RE_SCORE = re.compile(r'(?:score|rating|badge)[^>]*>\s*([\d.]{1,4})\s*<', re.I)

# PoW 挑战页特征
_RE_POW_HASH = re.compile(r"var\s+hash\s*=\s*['\"]([a-f0-9]{40})['\"]")
_RE_POW_TARGET = re.compile(r"var\s+target\s*=\s*['\"]([a-f0-9]{40})['\"]")

# 分页模板: {tid} 类型 -> 分类路径, {page} = 页码
CAT_TPLS = {
    'wd': '/listnew/wd-{page}.html',
    '1': '/cat/1-{page}.html',
    '6': '/medialist/id/6-{page}.html',
    '7': '/cat/7-{page}.html',
    '8': '/medialist/id/8-{page}.html',
    '9': '/medialist/id/9-{page}.html',
    '10': '/medialist/id/10-{page}.html',
    '11': '/medialist/id/11-{page}.html',
    '41': '/medialist/id/41-{page}.html',
    '12': '/medialist/id/12-{page}.html',
    '39': '/medialist/id/39-{page}.html',
    '2': '/cat/2-{page}.html',
    '13': '/cat/13-{page}.html',
    '14': '/medialist/id/14-{page}.html',
    '15': '/medialist/id/15-{page}.html',
    '16': '/medialist/id/16-{page}.html',
    '22': '/medialist/id/22-{page}.html',
    '21': '/medialist/id/21-{page}.html',
    '20': '/medialist/id/20-{page}.html',
    '23': '/medialist/id/23-{page}.html',
    '3': '/cat/3-{page}.html',
    '25': '/cat/25-{page}.html',
    '26': '/medialist/id/26-{page}.html',
    '27': '/medialist/id/27-{page}.html',
    '28': '/medialist/id/28-{page}.html',
    '4': '/cat/4-{page}.html',
    '29': '/cat/29-{page}.html',
    '30': '/medialist/id/30-{page}.html',
    '42': '/medialist/id/42-{page}.html',
    '40': '/cat/40-{page}.html',
}
SEARCH_TPL = ''
HAS_SUGGEST = True
DETAIL_PREFIX = '/video/'
LIST_PREFIXES = ['/medialist/id/', '/video/']

_LINE_PRIORITY = ['vip', '1080zyk', 'bfzym3u8', 'ffm3u8', 'lzm3u8', 'modum3u8', 'jsm3u8', 'mtm3u8']
_LINE_ALIAS = {
    'vip': 'VIP线路', '1080zyk': '1080资源', 'bfzym3u8': '暴风资源',
    'ffm3u8': '非凡M3U8', 'lzm3u8': '量子M3U8', 'modum3u8': '魔都M3U8',
    'jsm3u8': '极速M3U8', 'mtm3u8': '茅台M3U8',
}


class Spider(Spider):

    def getName(self):
        return '火龙果影视'

    site_name = '火龙果影视'
    _session = None

    @property
    def _sess(self):
        if getattr(self, '_session', None) is None:
            try:
                import requests
                s = requests.Session()
                s.verify = False
                s.headers.update(self.headers)
                self._session = s
            except Exception:
                self._session = None
        return self._session

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
        self.log("init:", self.site_url)

    def _solve_pow(self, html):
        m1 = _RE_POW_HASH.search(html)
        m2 = _RE_POW_TARGET.search(html)
        if not m1 or not m2:
            return None
        prefix_b = m1.group(1).encode()
        target = m2.group(1)
        start = time.time()
        for i in range(10 * 1000 * 1000):
            if hashlib.sha1(prefix_b + str(i).encode()).hexdigest() == target:
                self.log("PoW 破解成功:", i, "耗时 %.2fs" % (time.time() - start))
                return i
            if (i + 1) % 1000000 == 0 and time.time() - start > 60:
                self.log("PoW 超时")
                return None
        return None

    def _raw(self, url, timeout=30, headers=None, allow_redirects=True):
        h = dict(self.headers)
        if headers:
            h.update(headers)
        fn = getattr(self, "fetch", None)
        if callable(fn):
            try:
                return fn(url, headers=h, timeout=timeout, allow_redirects=allow_redirects)
            except TypeError:
                try:
                    return fn(url, headers=h, timeout=timeout)
                except Exception:
                    pass
            except Exception:
                pass
        s = self._sess
        if s is None:
            raise RuntimeError("no http client")
        return s.get(url, headers=h, timeout=timeout, allow_redirects=allow_redirects)

    def _fetch(self, url, timeout=30, headers=None):
        try:
            rsp = self._raw(url, timeout, headers)
            text = rsp.text if hasattr(rsp, "text") else (
                rsp.content.decode("utf-8", "ignore") if hasattr(rsp, "content") else str(rsp))
            if "attack_key" in text and "sha1(hash" in text:
                self.log("遇到 PoW 挑战")
                key = self._solve_pow(text)
                if key is not None:
                    sep = "&" if "?" in url else "?"
                    text = self._fetch(url + sep + "attack_key=" + str(key), timeout, headers)
                return text
            return text
        except Exception as e:
            self.log("fetch FAIL", url, e)
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
        s = _html.unescape(s)
        return re.sub(r"[ \t\r\f\v]+", " ", s).strip()

    def _norm_id(self, href):
        """把列表页链接统一成详情页链接，不同前缀的同一 id 归一化。"""
        href = (href or "").split("?")[0].strip()
        if not href:
            return ""
        if href.startswith("http"):
            return href
        m = re.match(r"^(/[A-Za-z0-9_\-]+/)(\d+)", href)
        if m:
            seg = m.group(1)
            for p in LIST_PREFIXES:
                if seg == p:
                    return DETAIL_PREFIX + m.group(2) + ".html"
            return DETAIL_PREFIX + m.group(2) + ".html"
        return href

    def _extract_videos(self, html):
        if not html:
            return []
        buckets = {}
        for m in _RE_CARD.finditer(html[:400000]):
            href, attrs, inner = m.group(1), m.group(2), m.group(3)
            href = href.replace("&amp;", "&").strip()
            if not href or href.startswith("#") or _RE_PLAY_HREF.search(href):
                continue
            key = re.sub(r"\d+", "#", href.split("?")[0])
            buckets.setdefault(key, []).append((href, attrs, inner))
        if not buckets:
            return []
        def _score(item):
            k, arr = item
            return (len(arr), len(k.strip('/').split('/')), -len(k))
        best = max(buckets.items(), key=_score)[1]
        if len(best) < 2 and len(buckets) > 1:
            all_items = []
            for arr in buckets.values():
                all_items.extend(arr)
            best = all_items
        merged, order = {}, []
        for href, attrs, inner in best[:400]:
            vid = self._norm_id(href)
            if not vid:
                continue
            name = self._pick_name(attrs, inner)
            pic = self._pick_pic(attrs, inner)
            rem = self._pick_remarks(inner, name)
            it = merged.get(vid)
            if it is None:
                it = {"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_remarks": ""}
                merged[vid] = it
                order.append(vid)
            if name and (not it["vod_name"] or len(name) > len(it["vod_name"])):
                it["vod_name"] = name
            if pic and not it["vod_pic"]:
                it["vod_pic"] = pic
            if rem and not it["vod_remarks"]:
                it["vod_remarks"] = rem
        videos = []
        for vid in order:
            it = merged[vid]
            if not it["vod_name"]:
                tail = vid.rstrip(".html")
                it["vod_name"] = tail.rsplit("/", 1)[-1]
            if it["vod_remarks"] == it["vod_name"]:
                it["vod_remarks"] = ""
            it["vod_pic"] = self._fix_url(it["vod_pic"]) or self.default_pic
            videos.append(it)
        return videos

    def _pick_name(self, attrs, inner):
        for rx in (r'title="([^"]*)"', r'alt="([^"]*)"'):
            m = re.search(rx, attrs, re.I)
            if m and m.group(1).strip():
                return self._clean(m.group(1))[:120]
        m = _RE_IMG.search(inner)
        if m:
            for g in (m.group(1), m.group(2)):
                s = self._clean(g)
                if s and not re.search(r'\.(jpg|png|webp|jpeg|gif)$', s, re.I):
                    return s[:120]
        s = self._clean(inner)
        return s[:120]

    def _pick_pic(self, attrs, inner):
        ms = re.search(r'background(?:-image)?\s*:\s*url\(([^)]+)\)', attrs + " " + inner, re.I)
        if ms:
            u = ms.group(1).strip("'\" ")
            if re.search(r'\.(jpg|png|webp|jpeg|gif)', u, re.I) and not re.search(r'favicon|/logo|placeholder', u, re.I):
                return u
        for blob in (attrs, inner):
            m = re.search(r'(?:data-original|data-src|data-lazy-src|data-echo|src)="([^"]+)"', blob, re.I)
            if not m:
                continue
            u = m.group(1)
            if not re.search(r'\.(jpg|png|webp|jpeg|gif)', u, re.I):
                continue
            if re.search(r'favicon|/logo|loading|load\.gif|/statics/img|placeholder', u, re.I):
                continue
            return u
        m = re.search(r"url\([\"']?([^\"')]+)", inner, re.I)
        return m.group(1) if m else ""

    def _pick_remarks(self, inner, name=""):
        for m in re.finditer(r'<(span|em|i|b)[^>]*>([^<]{1,20})</\1>', inner, re.I):
            s = self._clean(m.group(2))
            if not s or len(s) < 2:
                continue
            if re.search(r'\d{2,4}-\d{1,2}-\d{1,2}', s):
                continue
            if s in (self.site_name, "播放", "立即播放", "详情", "HD", "推荐",
                     "热门", "最新", "精选", "更多", "排行榜", "预告"):
                continue
            if name and s == name:
                continue
            return s[:20]
        return ""

    def _page_count(self, html):
        for m in _PAGEBOX_RE.finditer(html):
            nums = re.findall(r'>\s*(\d{1,5})\s*<', m.group(1))
            nums += re.findall(r'[?&]page=(\d{1,5})', m.group(1))
            nums += re.findall(r'-(\d{1,5})(?:-+)?\.html', m.group(1))
            vals = [int(x) for x in nums if x.isdigit() and 0 < int(x) < 100000]
            if vals:
                return max(vals)
        pages = re.findall(r"[?&]page=(\d+)", html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        m = re.search(r"(?:共|总共)\s*(\d{1,5})\s*页", html)
        if m:
            return int(m.group(1))
        return 999

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
        extend = extend or {}
        ext = {k: v for k, v in extend.items()
               if v not in ("", None, "全部") and k not in ("class",)}
        base = CAT_TPLS.get(str(tid))
        if not base:
            base = "/listnew/%s-{page}.html" % tid
        path = base.replace("{page}", str(page))
        url = self.site_url + path
        # 筛选参数挂到 query（多数站点兼容，不影响基础分页）
        if ext:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(ext)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pc = self._page_count(html) if html else 1
        return {"list": videos, "page": page, "pagecount": pc, "limit": 24, "total": pc * 24}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        try:
            u = self.site_url + "/index.php/ajax/suggest?mid=1&wd=" + urllib.parse.quote(key) + "&pg=" + str(page)
            rsp = self._fetch(u, timeout=10)
            data = json.loads(rsp)
            out = []
            for it in (data.get("list") or []):
                vid = str(it.get("id", ""))
                out.append({"vod_id": DETAIL_PREFIX + vid + ".html",
                            "vod_name": it.get("name", ""),
                            "vod_pic": self._fix_url(self._unesc(it.get("pic", ""))) or self.default_pic,
                            "vod_remarks": ""})
            if out:
                return {"list": out, "page": page, "pagecount": int(data.get("pagecount") or 1),
                        "limit": 20, "total": int(data.get("total") or len(out))}
        except Exception as e:
            self.log("suggest fail", e)
        url = self.site_url + "/search?wd=" + urllib.parse.quote(key) + "&page=" + str(page)
        html = self._fetch(url)
        return {"list": self._extract_videos(html), "page": page,
                "pagecount": self._page_count(html), "limit": 24, "total": 999}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        html = self._fetch(url)
        if not html:
            return {"list": []}
        name = ""
        h1s = [self._clean(x) for x in _RE_H1.findall(html)]
        h1s = [x for x in h1s if x and len(x) <= 120 and x != self.site_name]
        if h1s:
            name = max(h1s, key=len)
        if not name:
            m = _RE_TITLE_TAG.search(html)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id
        pic = self.default_pic
        m = _RE_OG_IMG.search(html)
        if m:
            pic = self._fix_url(m.group(1))
        else:
            m = _RE_PIC.search(html)
            if m:
                pic = self._fix_url(m.group(1))
        content = ""
        for rx in (_RE_INTRO, _RE_META_DESC):
            m = rx.search(html)
            if m and self._clean(m.group(1)):
                content = self._clean(m.group(1))
                break
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX
        director = actor = score = ""
        plain = self._clean(html)
        m = _RE_DIRECTOR.search(plain)
        if m:
            director = m.group(1).strip()
        m = _RE_ACTOR.search(plain)
        if m:
            actor = m.group(1).strip()
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)
        groups = {}
        seen_eps = set()
        for m in _RE_EPISODE_A.finditer(html):
            href, attrs, inner = m.group(1), m.group(2), m.group(3)
            href = href.replace("&amp;", "&").strip()
            mo = _RE_DATA_ORIGIN.search(attrs)
            origin = mo.group(1).strip() if mo else ""
            if not origin:
                ms = _RE_EP_ORIGIN_URL.search(href)
                if ms:
                    origin = "线路" + ms.group(1)
            if not origin and "/play/" in href:
                origin = (href.split("/play/")[-1].split("/")[0]) or "线路1"
            if not origin:
                continue
            if re.match(r'\s*javascript', href, re.I):
                continue
            url = href if href.startswith("http") else self.site_url + href
            if url in seen_eps:
                continue
            seen_eps.add(url)
            ep = ""
            mt = _RE_DATA_TITLE.search(attrs)
            if mt:
                ep = self._clean(mt.group(1))
            if not ep:
                ep = self._clean(inner)
            if not ep or len(ep) > 40:
                ep = "第%d集" % (len(groups.get(origin, [])) + 1)
            groups.setdefault(origin, []).append((ep, url))
        if not groups:
            return {"list": []}
        origins = sorted(groups.keys(),
                         key=lambda x: _LINE_PRIORITY.index(x) if x in _LINE_PRIORITY else 999)
        play_from, play_url = [], []
        for o in origins:
            play_from.append(_LINE_ALIAS.get(o, o))
            play_url.append("#".join("%s$%s" % (n, h) for n, h in groups[o]))
        return {"list": [{
            "vod_id": vod_id, "vod_name": name, "vod_pic": pic,
            "vod_content": content, "vod_actor": actor, "vod_director": director,
            "vod_score": score, "vod_remarks": "%d条线路" % len(groups),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res
        html = self._fetch(play_page)
        api_url = self._extract_api(html)

        if api_url:
            if api_url.startswith("http") and ".m3u8" in api_url.lower():
                res = {"parse": 0, "playUrl": "", "url": api_url,
                       "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
                self._play_cache[play_page] = (now, res)
                return res
            if api_url.startswith("/"):
                api_url = self.site_url + api_url
            real = self._resolve_to_real_m3u8(api_url, referer=play_page)
            if real:
                res = {"parse": 0, "playUrl": "", "url": real,
                       "header": {"User-Agent": UA, "Referer": self._box_referer()}}
                self._play_cache[play_page] = (now, res)
                return res
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def _box_referer(self):
        return self.site_url + "/"

    @staticmethod
    def _unesc(u):
        if not u:
            return ""
        u = u.replace("\\/", "/").replace("\\u0026", "&").replace("\\u003d", "=")
        u = u.replace("\\u002F", "/").replace("\\u002f", "/")
        u = u.replace("&amp;", "&")
        return u.strip()

    def _extract_api(self, html):
        if not html:
            return ""
        m = re.search(r"JSON\.parse\(\s*'([\s\S]{10,4000}?)'\s*\)", html)
        if m:
            raw = self._unesc(m.group(1))
            try:
                return self._unesc(json.loads(raw).get("url", ""))
            except Exception:
                m2 = re.search(r'"url"\s*:\s*"([^"]+)"', m.group(1))
                if m2:
                    return self._unesc(m2.group(1))
        m = re.search(r"player_\w*\s*=\s*\{[\s\S]{0,3000}?\}", html)
        if m:
            m2 = re.search(r'"url"\s*:\s*"([^"]+)"', m.group(0))
            if m2:
                return self._unesc(m2.group(1))
        m = re.search(r"(?:src|url|source|video)\s*[:=]\s*['\"]([^'\"]*(?:\.m3u8|/api/m3u8)[^'\"]*)", html, re.I)
        return self._unesc(m.group(1)) if m else ""

    def _resolve_to_real_m3u8(self, api_url, referer=None):
        try:
            rsp = self._raw(api_url, timeout=15, headers={"User-Agent": UA,
                              "Referer": referer or (self.site_url + "/")}, allow_redirects=False)
        except Exception as e:
            self.log("resolve fail", e)
            return ""
        loc = ""
        if hasattr(rsp, "headers") and rsp.headers:
            loc = rsp.headers.get("Location") or rsp.headers.get("location") or ""
        if not loc:
            txt = getattr(rsp, "text", "") or ""
            return api_url if "#EXTM3U" in txt else ""
        if loc.startswith("//"):
            loc = "https:" + loc
        loc = loc.replace("&amp;", "&")
        try:
            rsp2 = self._raw(loc, timeout=15, headers={"User-Agent": UA, "Referer": api_url})
            txt2 = getattr(rsp2, "text", "") or ""
        except Exception as e:
            self.log("master fail", e)
            return loc
        if "#EXTM3U" not in txt2:
            return loc
        lines = [x.strip() for x in txt2.split("\n") if x.strip()]
        base = self._box_referer()[:-1] or loc.rsplit("/", 1)[0]
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines):
                sub = lines[i + 1].strip()
                if sub.startswith("http"):
                    return sub
                return base + "/" + sub.lstrip("/")
        return loc

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
            rsp = self._raw(url, timeout=15, headers={"User-Agent": UA,
                              "Referer": self.site_url + "/"})
            ctype = rsp.headers.get("Content-Type", "image/jpeg") if hasattr(rsp, "headers") else "image/jpeg"
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, rsp.content if hasattr(rsp, "content") else b"", ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()

