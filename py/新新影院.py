# coding=utf-8
"""
新新影院 xvjtnl.woosa.cn | TVBox Python 爬虫
架构: 苹果CMS V10 + MyTheme (six 模板)
关键:
  - 首页: /
  - 分类: /genre/{id}.html, 分页 /genre/{id}/page/{n}.html
  - 更多: /filter/id/{id}.html
  - 详情: /film/g{id}.html
  - 播放: /watch/g{id}/{sid}/{nid}.html, player_aaaa.url 即 m3u8
  - 搜索: /lookup.html?wd={kw}
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
                print("[woosa]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://xvjtnl.woosa.cn"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/six/statics/img/favicon.ico"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 顶级分类（从首页确认）
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺片"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "24", "type_name": "短剧"},
]

# 电影子分类（从首页/分类页提取）
_SUB_CLASS = {
    "1":  [("6", "动作片"), ("7", "喜剧片"), ("8", "爱情片"), ("9", "科幻片"),
           ("10", "剧情片"), ("11", "战争片"), ("12", "纪录片"), ("39", "恐怖片"),
           ("41", "动画片")],
    "2":  [("13", "国产剧"), ("14", "香港剧"), ("15", "韩国剧"), ("16", "欧美剧"),
           ("22", "台湾剧"), ("21", "日本剧"), ("20", "泰国剧"), ("23", "海外剧")],
    "3":  [],
    "4":  [],
    "24": [],
}

# ---- 以下三块是"筛选面板"的选项，从分类页源码提取 ----
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "内地", "v": "内地"}, {"n": "韩国", "v": "韩国"},
    {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
    {"n": "日本", "v": "日本"}, {"n": "美国", "v": "美国"},
    {"n": "泰国", "v": "泰国"}, {"n": "英国", "v": "英国"},
    {"n": "新加坡", "v": "新加坡"}, {"n": "其他", "v": "其他"},
]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)]

_LANGS = [
    {"n": "全部", "v": ""},
    {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"},
    {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"},
    {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"},
    {"n": "其它", "v": "其它"},
]

_SORTS = [{"n": "时间", "v": "time"},
          {"n": "人气", "v": "hits"},
          {"n": "评分", "v": "score"}]

_PLOT_TV = ["全部", "古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪",
            "动作", "奇幻", "剧情", "历史", "经典", "乡村", "情景",
            "商战", "网剧", "其他"]
_PLOT_MOVIE = ["全部", "喜剧", "爱情", "恐怖", "科幻", "动作", "战争",
               "犯罪", "悬疑", "奇幻", "剧情", "动画", "文艺", "纪录", "其他"]


class Spider(Spider):

    def getName(self):
        return "新新影院"

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
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础工具 ----------------

    def _fetch(self, url, timeout=15, headers=None):
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
        url = url.strip().replace("&amp;", "&")
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

    # ---------------- 列表解析 ----------------

    def _extract_videos(self, html):
        """
        从首页/分类页/搜索页提取影片卡片。
        """
        videos = []
        seen = set()
        if not html:
            return videos

        start_re = re.compile(r'<a[^>]*iqy-vodlist__thumb', re.I)
        href_re = re.compile(r'href="(/film/g[^"]+?\.html)"', re.I)
        title_re = re.compile(r'title="([^"]*)"', re.I)
        pic_re = re.compile(r'data-original="([^"]*)"', re.I)
        remark_re = re.compile(
            r'<span[^>]*class="pic-text[^"]*"[^>]*>([^<]*)</span>', re.I)
        next_re = re.compile(r'<a[^>]*iqy-vodlist__thumb|</li>', re.I)

        starts = [m.start() for m in start_re.finditer(html)]
        for s in starts:
            next_m = next_re.search(html, s + 10)
            e = next_m.start() if next_m else s + 1000
            if e - s > 1000:
                e = s + 1000
            seg = html[s:e]

            hm = href_re.search(seg)
            if not hm:
                continue
            tm = title_re.search(seg)
            pm = pic_re.search(seg)
            rm = remark_re.search(seg)

            href = hm.group(1).replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)

            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(tm.group(1))[:100] if tm else href,
                "vod_pic":     self._fix_url(pm.group(1)) if pm else self.default_pic,
                "vod_remarks": self._clean(rm.group(1)) if rm else "",
            })

        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = [int(x) for x in re.findall(r'/page/(\d+)', html)]
        if pages:
            return max(pages)
        return 1

    # ---------------- 首页 / 分类 / 搜索 ----------------

    def homeContent(self, filter=False):
        FILTERS = {}
        for c in CLASSES:
            tid = c["type_id"]
            sub = [{"n": "全部", "v": ""}] + \
                  [{"n": n, "v": sid} for sid, n in _SUB_CLASS.get(tid, [])]
            plot_list = _PLOT_MOVIE if tid == "1" else _PLOT_TV
            plot = [{"n": p, "v": "" if p == "全部" else p} for p in plot_list]
            FILTERS[tid] = [
                {"key": "class", "name": "分类", "value": sub},
                {"key": "plot",  "name": "剧情", "value": plot},
                {"key": "area",  "name": "地区", "value": _AREAS},
                {"key": "year",  "name": "年份", "value": _YEARS},
                {"key": "lang",  "name": "语言", "value": _LANGS},
                {"key": "by",    "name": "排序", "value": _SORTS},
            ]
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

        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        cid = extend.pop("class", "") or tid

        if cid in ("1", "2", "3", "4", "24"):
            path = "/genre/%s.html" % cid
            if page and page > 1:
                path = "/genre/%s/page/%d.html" % (cid, page)
        else:
            path = "/filter/id/%s.html" % cid
            if page and page > 1:
                path = "/filter/id/%s/page/%d.html" % (cid, page)

        url = self.site_url + path
        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  got %d videos, pagecount=%d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = "%s/lookup.html?wd=%s" % (self.site_url, urllib.parse.quote(key))
        if page > 1:
            url = "%s/lookup/wd/%s/page/%d.html" % (
                self.site_url, urllib.parse.quote(key), page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {"list": videos, "page": page, "pagecount": 1,
                "limit": 24, "total": len(videos)}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 ----------------

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题：<h1 class="title">老舅</h1>
        name = ""
        m = re.search(r'<h1[^>]*class="title"[^>]*>([\s\S]*?)</h1>', html, re.I)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r'<title>(.*?)</title>', html, re.S)
            if m:
                name = self._clean(m.group(1).split("-")[0].split("_")[0])
        name = name.strip() or vod_id

        # 封面：og:image
        pic = self.default_pic
        m = re.search(
            r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
            html, re.I)
        if m:
            pic = self._fix_url(m.group(1))

        # 简介
        content = ""
        m = re.search(
            r'<span[^>]*class="data"[^>]*>\s*<p>([\s\S]*?)</p>\s*</span>',
            html, re.I)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(r'<span[^>]*class="sketch[^"]*"[^>]*>([\s\S]*?)</span>',
                          html, re.I)
            if m:
                content = self._clean(m.group(1))
        if not content:
            m = re.search(
                r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
                html, re.I)
            if m:
                content = self._clean(m.group(1))
        content = INTRO_PREFIX + "\n" + content if content else INTRO_PREFIX

        # 主演：<p class="data"><span class="text-muted">主演：</span><a>史彭元</a>&nbsp;<a>杨烁</a>...</p>
        actor = ""
        m = re.search(
            r'<p[^>]*class="data"[^>]*>\s*<span[^>]*class="text-muted"[^>]*>主演：</span>([\s\S]*?)</p>',
            html, re.I)
        if m:
            names = re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1))
            if names:
                actor = ", ".join(n.strip() for n in names if n.strip())
            else:
                actor = self._clean(m.group(1))

        # 导演：<p class="data"><span class="text-muted">导演：</span><a>五百</a>&nbsp;<a>陈泳旭</a>...</p>
        director = ""
        m = re.search(
            r'<p[^>]*class="data"[^>]*>\s*<span[^>]*class="text-muted"[^>]*>导演：</span>([\s\S]*?)</p>',
            html, re.I)
        if m:
            names = re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1))
            if names:
                director = ", ".join(n.strip() for n in names if n.strip())
            else:
                director = self._clean(m.group(1))

        # 备注："更新：全30集/2026-07-20"
        remarks = ""
        m = re.search(
            r'<p[^>]*class="data"[^>]*>\s*<span[^>]*class="text-muted"[^>]*>更新：</span>'
            r'\s*<span[^>]*class="text-red"[^>]*>([\s\S]*?)</span>',
            html, re.I)
        if m:
            remarks = self._clean(m.group(1))
        if not remarks:
            m = re.search(
                r'<span[^>]*class="pic-text[^"]*"[^>]*>([^<]*)</span>',
                html, re.I)
            if m:
                remarks = self._clean(m.group(1))

        # 播放源线路
        play_from = []
        play_url = []

        tabs = re.findall(
            r'<li[^>]*>\s*<a[^>]*href="(#playlist\d+)"[^>]*data-toggle="tab"[^>]*>([^<]+)</a>',
            html, re.I)

        for tab_id, tab_name in tabs:
            pid = tab_id.lstrip("#")
            m = re.search(
                r'<div[^>]*id="%s"[^>]*>([\s\S]*?)</div>' % re.escape(pid),
                html, re.I)
            if not m:
                continue
            block = m.group(1)

            eps = []
            for em in re.finditer(
                    r'<a[^>]*href="(/watch/[^"]+?\.html)"[^>]*>([^<]+)</a>',
                    block, re.S | re.I):
                ep_url, ep_name = em.group(1), em.group(2).strip()
                if not ep_url.startswith("http"):
                    ep_url = self.site_url + ep_url
                eps.append((ep_name, ep_url))

            if eps:
                play_from.append(self._clean(tab_name))
                play_url.append("#".join("%s$%s" % (n, u) for n, u in eps))

        if not play_from:
            self.log("  no play lines found")
            return {"list": []}

        return {"list": [{
            "vod_id":       vod_id,
            "vod_name":     name,
            "vod_pic":      pic,
            "vod_content":  content,
            "vod_actor":    actor,      # ← 新增
            "vod_director": director,   # ← 新增
            "vod_remarks":  remarks or ("%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ---------------- 播放 ----------------

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

        if html:
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>',
                          html, re.S)
            if m:
                try:
                    obj = json.loads(m.group(1))
                    m3u8 = obj.get("url", "") or ""
                except Exception as e:
                    self.log("player_aaaa 解析失败: %s" % e)

        if m3u8:
            m3u8 = m3u8.replace("\\/", "/").replace("&amp;", "&")
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
            return res

        res = {
            "parse": 1, "playUrl": "", "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }
        self._play_cache[play_page] = (now, res)
        return res

    # ---------------- 其他 ----------------

    def localProxy(self, param):
        return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
