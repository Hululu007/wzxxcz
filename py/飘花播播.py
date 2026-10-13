# coding=utf-8
"""
飘花播播 7itv.com | TVBox Python 爬虫
结构依据：MacCMS + mxtheme 模板
- 详情页 /voddetail/{id}.html
- 播放页 /vodplay/{id}-{sid}-{nid}.html
- player_aaaa.url 为 Base64(URL编码) 的 m3u8 地址
- 搜索 /vodsearch/{wd}-------------.html ，有5秒频率限制
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
                a = _rq.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', a)
                self._session.mount('http://', a)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[7itv]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.7itv.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/mxtheme/images/logo.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 分类：来自导航栏 /vodtype/{id}.html
CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "剧集"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "5", "type_name": "短剧"},
]

# 线路别名（来自播放页 module-tab-item 文本 + player_aaaa.from）
_LINE_ALIAS = {
    "lzm3u8": "量子云",
    "wjm3u8": "无尽云",
    "snm3u8": "索尼",
    "ffm3u8": "非凡云",
}
_LINE_PRIORITY = ["lzm3u8", "wjm3u8", "snm3u8", "ffm3u8"]

# 筛选（vodshow URL 段位：/vodshow/{class}--------{area}-{year}.html 类 MacCMS 规则）
_SORTS = [{"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}]
_YEARS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
    {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"},
    {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"},
    {"n": "泰国", "v": "泰国"}, {"n": "英国", "v": "英国"},
]

# 子分类（来自 /vodshow/13---国产剧--------.html 中的 tag）
_FILTERS_MAP = {
    "1": ["全部", "动作片", "喜剧片", "爱情片", "科幻片", "恐怖片", "剧情片", "战争片", "纪录片", "其他片"],
    "2": ["全部", "国产剧", "港台剧", "日韩剧", "欧美剧", "海外剧"],
    "3": ["全部", "国产综艺", "港台综艺", "日韩综艺", "欧美综艺"],
    "4": ["全部", "国漫", "日漫", "欧美动漫"],
    "5": ["全部", "短剧", "AI漫剧"],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "分类",
         "value": [{"n": x, "v": "" if x == "全部" else x} for x in _FILTERS_MAP.get(tid, ["全部"])]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]


# ============ 正则 ============
# 列表卡片：<a href="/voddetail/xxx.html" title="名称" class="module-poster-item module-item">
#   <div class="module-item-cover"><div class="module-item-note">更新至xx</div>
#   <div class="module-item-pic"><img ... data-original="pic" alt="名称">
_RE_CARD = re.compile(
    r'<a\s+href="(/voddetail/\d+\.html)"[^>]*?title="([^"]*)"[^>]*?class="[^"]*module-poster-item[^"]*"'
    r'[\s\S]{0,400}?'
    r'(?:<div class="module-item-note">([^<]*)</div>)?'
    r'[\s\S]{0,200}?'
    r'<img[^>]*?(?:data-original|src)="([^"]*)"',
    re.S | re.I)

# 兜底：只抓 href 与 title
_RE_CARD_A = re.compile(
    r'<a\s+href="(/voddetail/\d+\.html)"[^>]*?title="([^"]*)"',
    re.I)

# 详情页字段
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_PIC = re.compile(r'data-original="(/upload/vod/[^"]+)"', re.I)
_RE_INTRO = re.compile(
    r'<div class="module-info-introduction-content">([\s\S]*?)</div>',
    re.S | re.I)
_RE_DIRECTOR = re.compile(
    r'<span class="module-info-item-title">导演：</span>([\s\S]*?)</div>', re.S | re.I)
_RE_ACTOR = re.compile(
    r'<span class="module-info-item-title">主演：</span>([\s\S]*?)</div>', re.S | re.I)
_RE_UPDATE = re.compile(
    r'<span class="module-info-item-title">更新：</span>\s*<div[^>]*>([^<]*)</div>', re.I)
_RE_EPISODE_CNT = re.compile(
    r'<span class="module-info-item-title">集数：</span>\s*<div[^>]*>([^<]*)</div>', re.I)
_RE_A_TAG = re.compile(r'<a[^>]*>([^<]*)</a>', re.I)

# 播放源 tab（详情页）：data-dropdown-value="量子云"
_RE_TAB = re.compile(
    r'<div class="module-tab-item tab-item"[^>]*data-dropdown-value="([^"]+)"[^>]*>'
    r'<span>([^<]+)</span><small>(\d+)</small>', re.I)

# 剧集链接：/vodplay/{id}-{sid}-{nid}.html
_RE_EP = re.compile(
    r'<a\s+class="module-play-list-link[^"]*"\s+href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*?title="([^"]*)"',
    re.I)

# 播放页 player_aaaa
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.S)

# 分页
_RE_PAGE = re.compile(r'/vodshow/[^"\']+?page/(\d+)', re.I)


class Spider(Spider):

    def getName(self):
        return "飘花播播"

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
        self._last_search_ts = 0
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------- 基础 ----------
    def _fetch(self, url, timeout=20, headers=None):
        h = dict(self.headers)
        if headers:
            h.update(headers)
        try:
            rsp = self.fetch(url, headers=h, timeout=timeout)
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

    def _extract_videos(self, html):
        videos, seen = [], set()
        if not html:
            return videos

        for m in _RE_CARD.finditer(html):
            href, title, note, pic = m.group(1), m.group(2), m.group(3) or "", m.group(4)
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(title)[:100],
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": self._clean(note),
            })

        if not videos:
            for href, title in _RE_CARD_A.findall(html):
                if href in seen:
                    continue
                seen.add(href)
                videos.append({
                    "vod_id": href,
                    "vod_name": self._clean(title)[:100],
                    "vod_pic": self.default_pic,
                    "vod_remarks": "",
                })
        return videos

    def _page_count(self, html, cur=1):
        if not html:
            return cur
        nums = []
        for m in _RE_PAGE.finditer(html):
            try:
                nums.append(int(m.group(1)))
            except Exception:
                pass
        return max(nums) if nums else cur

    # ---------- TVBox 接口 ----------
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

        # MacCMS: /vodshow/{子类id}--------{area}---{year}.html
        # 我们按 type_id 直接进 /vodtype/{tid}.html 再翻页，最稳
        # 带筛选时用 /vodshow/{tid}---{area}--------{year}.html
        area = extend.get("area") or ""
        year = extend.get("year") or ""
        sub = extend.get("class") or ""

        if sub or area or year:
            # 子分类需要走 vodshow，子分类名以搜索方式更稳，这里用 type + 参数
            url = "%s/vodshow/%s-%s--------%s.html" % (
                self.site_url, tid,
                urllib.parse.quote(area) if area else "",
                year)
        else:
            url = "%s/vodtype/%s.html" % (self.site_url, tid)

        if page > 1:
            url = url.replace(".html", "/page/%d.html" % page) if ".html" in url \
                else url + ("&" if "?" in url else "?") + "page=%d" % page

        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pc = self._page_count(html, page)
        return {"list": videos, "page": page, "pagecount": pc, "limit": 24, "total": pc * 24}

    def searchContent(self, key, quick, pg="1"):
        # 5秒频率限制，做防抖
        now = time.time()
        wait = 5 - (now - self._last_search_ts)
        if wait > 0:
            time.sleep(wait)
        self._last_search_ts = time.time()

        page = int(pg) if pg else 1
        wd = urllib.parse.quote(key)
        url = "%s/vodsearch/%s-------------.html" % (self.site_url, wd)
        if page > 1:
            url = url.replace(".html", "/page/%d.html" % page)
        self.log("search: %s" % url)
        html = self._fetch(url)

        # 命中拦截页直接返回空，避免污染
        if "请勿频繁操作" in html or "系统提示" in html:
            self.log("search 被限频拦截")
            return {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

        videos = self._extract_videos(html)
        return {"list": videos, "page": page,
                "pagecount": self._page_count(html, page),
                "limit": 24, "total": 999}

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

        # 标题
        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        # 简介
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # 导演 / 主演
        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            names = _RE_A_TAG.findall(m.group(1))
            director = ", ".join(self._clean(x) for x in names if self._clean(x))
        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            names = _RE_A_TAG.findall(m.group(1))
            actor = ", ".join(self._clean(x) for x in names if self._clean(x))

        # 备注
        remark = ""
        m = _RE_EPISODE_CNT.search(html)
        if m:
            remark = self._clean(m.group(1))
        else:
            m = _RE_UPDATE.search(html)
            if m:
                remark = "更新:" + self._clean(m.group(1))

        # 播放源分组：从 tab 拿源名，再从剧集 href 里按 sid 分组
        tab_names = {}  # sid -> 显示名（无 sid 数据，只做展示用，可忽略）
        # 剧集：/vodplay/{id}-{sid}-{nid}.html
        groups = {}
        for href, title in _RE_EP.findall(html):
            mm = re.search(r"/vodplay/\d+-(\d+)-(\d+)\.html", href)
            if not mm:
                continue
            sid = mm.group(1)
            ep_name = self._clean(title)
            if not ep_name:
                ep_name = "第%s集" % mm.group(2)
            groups.setdefault(sid, []).append((ep_name, self._fix_url(href)))

        if not groups:
            return {"list": []}

        # sid 排序：按线路优先级（用 sid 映射到名字后排序；未知 sid 排后）
        def sid_key(s):
            return int(s) if s.isdigit() else 999

        sorted_sids = sorted(groups.keys(), key=sid_key)

        play_from, play_url = [], []
        for sid in sorted_sids:
            eps = groups[sid]
            # 去重，保持顺序
            seen, uniq = set(), []
            for n, h in eps:
                if h in seen:
                    continue
                seen.add(h)
                uniq.append((n, h))
            # 源名：用 tab 里顺序对应的名字，没有就用 "线路{sid}"
            alias = _LINE_ALIAS.get(sid, "线路%s" % sid)
            play_from.append(alias)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in uniq))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_remarks": remark or ("%d条线路" % len(groups)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        real_url = ""
        header_ref = self.site_url + "/"

        m = _RE_PLAYER.search(html)
        if m:
            raw = m.group(1)
            try:
                data = json.loads(raw)
            except Exception:
                data = {}
            enc = data.get("url") or ""
            if enc:
                real_url = self._decode_player_url(enc)
            # 有的模板 url 里已是明文
            if not real_url and isinstance(enc, str) and enc.startswith("http"):
                real_url = enc

        if real_url:
            res = {
                "parse": 0,
                "playUrl": "",
                "url": real_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": header_ref,
                },
            }
            self._play_cache[play_page] = (now, res)
            self.log("=> m3u8: %s" % real_url[:160])
            return res

        # 兜底：交给 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": header_ref}}
        self._play_cache[play_page] = (now, res)
        return res

    def _decode_player_url(self, enc):
        """player_aaaa.url = Base64(URL编码后的 m3u8)"""
        if not enc:
            return ""
        try:
            s = urllib.parse.unquote(enc)
        except Exception:
            s = enc
        # 补 padding
        pad = len(s) % 4
        if pad:
            s += "=" * (4 - pad)
        try:
            raw = base64.b64decode(s).decode("utf-8", "ignore")
        except Exception:
            return ""
        # 解码后可能还是 URL 编码
        try:
            if "%" in raw:
                raw = urllib.parse.unquote(raw)
        except Exception:
            pass
        raw = raw.replace("\\/", "/").replace("&amp;", "&")
        return raw if raw.startswith("http") else ""

    # ---------- 杂项 ----------
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
