# coding=utf-8
"""
首映网 jiyaogroup.com | TVBox Python 爬虫
苹果CMS V10 标准站，播放页 player_aaaa 直链 m3u8，encrypt=0，parse=0
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
                print("[shouying]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://jiyaogroup.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/statics/img/favicon.ico"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 总分类（导航）
CLASSES = [
    {"type_id": "dianying",    "type_name": "电影"},
    {"type_id": "dianshiju",   "type_name": "电视剧"},
    {"type_id": "zongyi",      "type_name": "综艺"},
    {"type_id": "dongman",     "type_name": "动漫"},
    {"type_id": "donghuapian", "type_name": "动画片"},
    {"type_id": "duanju",      "type_name": "短剧"},
]

# 每个总分类对应的子分类（用于筛选 class 维度）
_SUB_CLASS = {
    "dianying":    ["dongzuopian", "xijupian", "aiqingpian", "kehuanpian", "kongbupian",
                    "juqingpian", "zhanzhengpian", "jilupian"],
    "dianshiju":   ["guochanju", "xianggangju", "taiwanju", "ribenju", "taiguoju",
                    "hanguoju", "oumeiju", "haiwaiju"],
    "zongyi":      ["daluzongyi", "gangtaizongyi", "rihanzongyi", "oumeizongyi"],
    "dongman":     ["guochandongman", "rihandongman", "gangtaidongman",
                    "oumeidongman", "haiwaidongman"],
    "donghuapian": ["donghuapian"],
    "duanju":      ["nvpinlianai", "fanzhuanshuangju", "niandaichuanyue", "naodongxuanyi",
                    "xiandaidushi", "guzhuangxianxia", "rexuejuqing"],
}

_SUB_NAME = {
    "dongzuopian": "动作片", "xijupian": "喜剧片", "aiqingpian": "爱情片",
    "kehuanpian": "科幻片", "kongbupian": "恐怖片", "juqingpian": "剧情片",
    "zhanzhengpian": "战争片", "jilupian": "纪录片",
    "guochanju": "国产剧", "xianggangju": "香港剧", "taiwanju": "台湾剧",
    "ribenju": "日本剧", "taiguoju": "泰国剧", "hanguoju": "韩国剧",
    "oumeiju": "欧美剧", "haiwaiju": "海外剧",
    "daluzongyi": "大陆综艺", "gangtaizongyi": "港台综艺", "rihanzongyi": "日韩综艺",
    "oumeizongyi": "欧美综艺",
    "guochandongman": "国产动漫", "rihandongman": "日韩动漫", "gangtaidongman": "港台动漫",
    "oumeidongman": "欧美动漫", "haiwaidongman": "海外动漫",
    "donghuapian": "动画片",
    "nvpinlianai": "女频恋爱", "fanzhuanshuangju": "反转爽剧", "niandaichuanyue": "年代穿越",
    "naodongxuanyi": "脑洞悬疑", "xiandaidushi": "现代都市", "guzhuangxianxia": "古装仙侠",
    "rexuejuqing": "热血剧情",
}

_SORTS = [{"n": "按时间", "v": "time"},
          {"n": "按人气", "v": "hits"},
          {"n": "按评分", "v": "score"}]
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "内地", "v": "内地"}, {"n": "大陆", "v": "大陆"},
    {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
    {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"},
    {"n": "韩国", "v": "韩国"}, {"n": "英国", "v": "英国"},
    {"n": "法国", "v": "法国"}, {"n": "泰国", "v": "泰国"},
    {"n": "印度", "v": "印度"}, {"n": "意大利", "v": "意大利"},
    {"n": "西班牙", "v": "西班牙"}, {"n": "加拿大", "v": "加拿大"},
    {"n": "德国", "v": "德国"}, {"n": "新加坡", "v": "新加坡"},
    {"n": "其他", "v": "其他"},
]
_LANGS = [
    {"n": "全部", "v": ""},
    {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"},
    {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"},
    {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"},
    {"n": "其它", "v": "其它"},
]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    subs = _SUB_CLASS.get(tid, [tid])
    FILTERS[tid] = [
        {"key": "class", "name": "分类",
         "value": [{"n": _SUB_NAME.get(s, s), "v": s} for s in subs]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "lang", "name": "语言", "value": _LANGS},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]


# ===================== 正则 =====================
# 列表卡片：兼容 data-original / src，href 后接 title，再接封面
_RE_CARD = re.compile(
    r'<a class="stui-vodlist__thumb lazyload"\s+href="(/voddetail/[^"]+)"\s+'
    r'title="([^"]*)"\s+data-original="([^"]*)"',
    re.S | re.I)

# 搜索卡片（media 布局）
_RE_SEARCH_CARD = re.compile(
    r'<a class="v-thumb stui-vodlist__thumb lazyload"\s+href="(/voddetail/[^"]+)"\s+'
    r'title="([^"]*)"\s+data-original="([^"]*)"',
    re.S | re.I)

_RE_HREF = re.compile(r'href="(/voddetail/[^"]+\.html)"', re.I)
_RE_IMG = re.compile(
    r'<a class="[^"]*stui-vodlist__thumb[^"]*"[^>]*?title="([^"]*)"[^>]*?'
    r'(?:data-original|src)="([^"]*)"', re.S | re.I)

# 详情页
_RE_H1 = re.compile(r'<h1 class="title">([\s\S]*?)</h1>', re.I)
_RE_H1_SCORE = re.compile(r'<span class="score[^"]*">([\d.]+)</span>', re.I)
_RE_INTRO = re.compile(
    r'<p class="desc hidden-xs">\s*<span class="left text-muted">简介：</span>'
    r'([\s\S]*?)</p>', re.S | re.I)
_RE_INTRO_TAIL = re.compile(r'想看更多的.*?请关注我们的网站：[\s\S]*$', re.S | re.I)
_RE_PIC = re.compile(
    r'<div class="stui-content__thumb">[\s\S]*?data-original="([^"]+)"', re.S | re.I)

_RE_DIRECTOR = re.compile(
    r'导演：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_ACTOR = re.compile(
    r'主演：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_TYPE = re.compile(r'类型：</span>([\s\S]*?)<span class="split-line">', re.S | re.I)
_RE_AREA = re.compile(r'地区：</span>([\s\S]*?)<span class="split-line">', re.S | re.I)
_RE_YEAR = re.compile(r'年份：</span>([\s\S]*?)</p>', re.S | re.I)

# 剧集：/vodplay/{拼音}-{线路}-{集}.html
_RE_EPISODE = re.compile(
    r'<li\s*[^>]*><a\s+href="(/vodplay/[^"]+?-(\d+)-(\d+)\.html)"'
    r'[^>]*title="([^"]+)"', re.I)
_RE_TAB = re.compile(
    r'<a data-toggle="tab" href="#down(\d+)">([^<]+)</a>', re.I)

# 播放页 player_aaaa
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)

# 分页
_RE_PAGE_NUM = re.compile(r'<span class="num">\d+/(\d+)</span>')
_RE_TAIL = re.compile(r'href="[^"]*?(\d+)\.html">尾页')

# 脏图过滤
_RE_BAD_PIC = re.compile(r'^(file:///|/|)$', re.I)


class Spider(Spider):

    def getName(self):
        return "首映网"

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
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=20, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
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

    def _valid_pic(self, url):
        url = (url or "").strip()
        if not url or _RE_BAD_PIC.match(url):
            return self.default_pic
        return self._fix_url(url)

    # ---------- URL 构建：11 段模板 ----------
    def _build_url(self, cid, area="", lang="", letter="", sort="", cls="", page=1, year=""):
        """
        /vodshow/{cid}-{area}-{lang}-{letter}-{sort}-{cls}--------{page}---{year}.html
        第 1 页 page 位留空（不填数字）
        """
        page_s = "" if (not page or int(page) <= 1) else str(int(page))
        return "%s/vodshow/%s-%s-%s-%s-%s-%s--------%s---%s.html" % (
            self.site_url, cid, area, lang, letter, sort, cls, page_s, year)

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for href, title, pic in _RE_CARD.findall(html) + _RE_SEARCH_CARD.findall(html):
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(title)[:100],
                "vod_pic":     self._valid_pic(pic),
                "vod_remarks": "",
            })
        if videos:
            return videos

        # 兜底：分开抓 href / img
        hrefs = _RE_HREF.findall(html)
        imgs = _RE_IMG.findall(html)
        for i, href in enumerate(hrefs):
            if href in seen:
                continue
            seen.add(href)
            title, pic = ("", "")
            if i < len(imgs):
                title, pic = imgs[i]
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(title)[:100] or href.split("/")[-1].replace(".html", ""),
                "vod_pic":     self._valid_pic(pic),
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = _RE_PAGE_NUM.search(html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        m = _RE_TAIL.search(html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return 999

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        # 首页卡片复用列表正则
        videos = self._extract_videos(html)
        # 首页还有大量轮播/榜单，用通用 href+img 兜底补全
        if len(videos) < 6:
            videos = self._extract_videos(html)
        self.log("home videos: %d" % len(videos))
        return {"list": videos}

    # ---------- 分类 ----------
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

        # tid 是总分类；extend.class 是子分类，没有则用 tid 对应的默认子分类
        cid = extend.get("class") or (_SUB_CLASS.get(tid) or [tid])[0]
        url = self._build_url(
            cid=cid,
            area=extend.get("area", ""),
            lang=extend.get("lang", ""),
            letter=extend.get("letter", ""),
            sort=extend.get("sort", "time"),
            cls="",
            page=page,
            year=extend.get("year", ""),
        )
        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  videos=%d pagecount=%d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 30, "total": pagecount * 30,
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        # 第 1 页：/vodsearch/-------------.html?wd=key
        # 第 N 页：/vodsearch/--------{N}---.html?wd=key（苹果CMS 标准）
        if page <= 1:
            url = "%s/vodsearch/-------------.html?wd=%s" % (self.site_url, kw)
        else:
            url = "%s/vodsearch/--------%d---.html?wd=%s" % (self.site_url, page, kw)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 30, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题 + 评分
        name = ""
        score = ""
        m = _RE_H1.search(html)
        if m:
            raw = m.group(1)
            ms = _RE_H1_SCORE.search(raw)
            if ms:
                score = ms.group(1)
            name = self._clean(re.sub(r'<span class="score[^"]*">[\d.]+</span>', '', raw))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("《")[-1].split("》")[0])
        name = name or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_PIC.search(html)
        if m:
            pic = self._valid_pic(m.group(1))

        # 简介
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if content:
            content = _RE_INTRO_TAIL.sub("", content).strip()
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 元信息
        def _grab(reg):
            mm = reg.search(html)
            if not mm:
                return ""
            return self._clean(re.sub(r"<[^>]+>", " ", mm.group(1))).strip(" ,，")

        director = _grab(_RE_DIRECTOR)
        actor = _grab(_RE_ACTOR)
        type_ = _grab(_RE_TYPE)
        area = _grab(_RE_AREA)
        year = _grab(_RE_YEAR)

        # ===== 剧集：按线路分组 =====
        # tab 名称：down1 -> 高清云播
        tabs = {}
        for m in _RE_TAB.finditer(html):
            tabs[m.group(1)] = self._clean(m.group(2))
        # 剧集：/vodplay/{拼音}-{line}-{ep}.html
        groups = {}
        for m in _RE_EPISODE.finditer(html):
            href, line, ep, ep_title = m.group(1), m.group(2), m.group(3), m.group(4)
            href = href.replace("&amp;", "&")
            full = href if href.startswith("http") else self.site_url + href
            ep_name = self._clean(ep_title) or ("第%s集" % ep)
            groups.setdefault(line, []).append((ep_name, full))

        if not groups:
            return {"list": []}

        play_from = []
        play_url = []
        for line in sorted(groups.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            eps = groups[line]
            alias = tabs.get(line) or ("线路%s" % line)
            play_from.append(alias)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_year": year,
            "vod_area": area,
            "vod_remarks": type_ or ("%d条线路" % len(groups)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        m3u8 = ""
        from_ = ""
        if html:
            m = _RE_PLAYER.search(html)
            if m:
                raw = m.group(1)
                try:
                    pa = json.loads(raw)
                    if int(pa.get("encrypt", 0) or 0) == 0:
                        m3u8 = pa.get("url", "") or ""
                    else:
                        # encrypt=1，URL 被加密，交给 TVBox 嗅探
                        m3u8 = ""
                    from_ = pa.get("from", "") or ""
                except Exception as e:
                    self.log("player_aaaa parse fail: %s" % e)

        if m3u8:
            res = {
                "parse": 0,
                "playUrl": "",
                "url": m3u8,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
            self._play_cache[play_page] = (now, res)
            self.log("  => m3u8: %s (from=%s)" % (m3u8[:160], from_))
            return res

        # 兜底：交给 TVBox 嗅探播放页
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
