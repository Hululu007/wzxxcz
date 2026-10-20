# coding=utf-8
"""
泡泡影院 www.zhonganedu.com | TVBox Python 爬虫
==================================================

【网站结构】
1) 频道导航：/class/1.html 电影、/class/2.html 电视剧、/class/3.html 综艺片、
   /class/4.html 动漫、/class/24.html 短剧

2) 列表卡片（首页 / 分类页 / 详情页“猜你喜欢”同构）：
   <li class="ff-vod-img-list ...">
     <a href="/celluloid/z9696775.html">
       <img data-original="https://.../xxx.jpg" src="/template/hl009/images/load.gif"
            alt="三国第一部：争洛阳">
       <div class="douban_score picrgot"><em class="label littplus">TC</em></div>
     </a>
     <h4 class="ff-text-hidden">
       <a href="/celluloid/z9696775.html" title="三国第一部：争洛阳">三国第一部：争洛阳</a>
   </li>
   真实封面在 data-original；src 恒为 load.gif 懒加载占位图。

3) 分页：/class/{分类ID}-{页}.html，第1页 /class/{分类ID}.html
   尾页给出总页数，例：<a href="/class/13-2630.html">尾页</a>
   注意：分类页的 {分类ID} 是分类id（如 13=国产剧），频道页是频道id（如 1=电影）。

4) 搜索：<form method="get" action="/query.html"><input name="wd">
   GET /query.html?wd=关键词

5) 筛选：/explore/... 组合路径，真实样本：
   /explore/id/13.html                     （频道/分类）
   /explore/class/古装/id/13.html          （类型）
   /explore/area/内地/id/13.html           （地区）
   /explore/id/13/year/2026.html           （年代）
   /explore/by/hits/id/13.html             （排序）

6) 详情页：
   标题  <h4><a href="/celluloid/z9696775.html" class="ff-text">片名</a></h4>
   主演  <dt>主演：</dt><dd class="ff-text-hidden ff-nb"><a ...>王凯</a>&nbsp;...
   状态  <dt>状态：</dt><dd class="ff-text-hidden" style="color:#FF0000">TC</dd>
   导演  <dt>导演：</dt><dd ...><a ...>谢君伟</a>&nbsp;</dd>
   地区  <dt class="hidden-xs">地区：</dt><dd ...><a ...>大陆</a></dd>
   年份  <dt>年份：</dt><dd><a href="/query/year/2026.html">2026</a></dd>
   简介  <div class="vod-content"> ... </div>   ← 完整的“剧情主线”正文
         （另有 <dd class="... vod-blurb"> 短简介，带“详细...”截断，不用它）

7) 线路与剧集（关键陷阱，已实测确认）：
   <ul ... class="... play-title">
     <li><a href="#playurl-tab-6" data-toggle="tab">...线路1</a></li>
     <li><a href="#playurl-tab-2" ...>线路2</a></li>
     <li class="active"><a href="#playurl-tab-1" ...>线路4</a></li>
     ...
   </ul>
   <div class="tab-pane" id="playurl-tab-6">
     <ul class="... play-list">
       <li><a class="btn ..." href="/playurl/z9696775/6/1.html" title="TC">TC</a></li>
     </ul>
   </div>
   → 界面上的“线路N”顺序与 sid 完全不同：线路1=sid6、线路4=sid1。
     因此必须从 tab 的 href="#playurl-tab-{sid}" 取 sid，绝不按序号推断。
   剧集链接：/playurl/{vodid}/{sid}/{nid}.html，文本在 title 属性里。

8) 播放页（真实源码）：
   <script>var player_aaaa={"flag":"play","encrypt":0,"url":"https://v.fengbao14.com/.../index.m3u8","from":"bfzym3u8","id":"969677","sid":6,"nid":1, ...}</script>
   → url 字段即直链 m3u8（已实测该地址返回 HTTP 200 且为合法 #EXTM3U 播放列表）。
     故 playerContent 直接解析 player_aaaa.url 返回 parse=0；
     解析不到时退回 parse=1 交给 TVBox 嗅探。
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
                print("[zhongan]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.zhonganedu.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

DEFAULT_PIC = HOST + "/template/hl009/images/load.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺片"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "24", "type_name": "短剧"},
]

# 各频道下的真实分类 (分类ID, 名称)，逐个 /class/{id}.html 页面“分类：”一行实测
CATS = {
    "1":  [("6", "动作片"), ("7", "喜剧片"), ("8", "爱情片"), ("9", "科幻片"),
           ("10", "剧情片"), ("11", "战争片"), ("41", "动画片"), ("12", "记录片"),
           ("39", "恐怖片")],
    "2":  [("13", "国产剧"), ("14", "香港剧"), ("15", "韩国剧"), ("16", "欧美剧"),
           ("22", "台湾剧"), ("21", "日本剧"), ("20", "泰国剧"), ("23", "海外剧")],
    "3":  [("25", "大陆综艺"), ("26", "日韩综艺"), ("27", "港台综艺"),
           ("28", "欧美综艺")],
    "4":  [("29", "国产动漫"), ("30", "日本动漫"), ("42", "港台动漫"),
           ("31", "欧美动漫"), ("43", "海外动漫")],
    "24": [("40", "短剧大全"), ("44", "AI漫剧")],
}

# 地区：严格取真实链接文本，/explore/area/{URL编码}/...
_AREAS = [("", "全部"), ("大陆", "大陆"), ("内地", "内地"), ("香港", "香港"),
          ("台湾", "台湾"), ("美国", "美国"), ("法国", "法国"), ("英国", "英国"),
          ("日本", "日本"), ("韩国", "韩国"), ("德国", "德国"), ("泰国", "泰国"),
          ("印度", "印度"), ("意大利", "意大利"), ("西班牙", "西班牙"),
          ("加拿大", "加拿大"), ("新加坡", "新加坡"), ("其他", "其他")]

_YEARS = [("", "全部")] + [(str(y), str(y)) for y in range(2026, 2000, -1)]

# 排序：hits 为真实链接 /explore/by/hits/id/13.html，time 为苹果CMS标准排序键
_SORTS = [("hits", "最多播放"), ("time", "最新更新")]

FILTERS = {}
for _c in CLASSES:
    _tid = _c["type_id"]
    FILTERS[_tid] = [
        {"key": "cat", "name": "分类",
         "value": [{"n": "全部", "v": ""}] +
                  [{"n": n, "v": i} for i, n in CATS.get(_tid, [])]},
        {"key": "area", "name": "地区",
         "value": [{"n": n, "v": v} for v, n in _AREAS]},
        {"key": "year", "name": "年代",
         "value": [{"n": n, "v": v} for v, n in _YEARS]},
        {"key": "by", "name": "排序",
         "value": [{"n": n, "v": v} for v, n in _SORTS]},
    ]


# ===================== 正则 =====================

_RE_LI = re.compile(r'<li\s+class="ff-vod-img-list[\s\S]*?</li>', re.I)
_RE_LINK = re.compile(r'href="(/celluloid/[^"]+?\.html)"', re.I)
_RE_IMG_DATA = re.compile(r'data-original="([^"]+)"', re.I)
_RE_IMG_ANY = re.compile(r'<img[^>]*?src="([^"]+)"', re.I)
_RE_ALT = re.compile(r'alt="([^"]*)"', re.I)
_RE_TITLE_ATTR = re.compile(r'title="([^"]*)"', re.I)
_RE_REMARKS = re.compile(
    r'<em[^>]*class="[^"]*littplus[^"]*"[^>]*>([^<]*)</em>', re.I)

# 详情页标题：<a href="/celluloid/xxx.html" class="ff-text">片名</a>
_RE_D_TITLE = re.compile(
    r'<a\s+href="/celluloid/[^"]+"\s+class="ff-text"[^>]*>([^<]+)</a>', re.I)
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TAG_TITLE = re.compile(r'<title>([\s\S]*?)</title>', re.I)

# 详情页 <dt>标签：</dt><dd ...>值</dd>
def _dt(label):
    return re.compile(
        r'<dt[^>]*>\s*' + label + r'\s*[：:]\s*</dt>\s*<dd[^>]*>([\s\S]*?)</dd>',
        re.I)

_RE_DT_ACTOR    = _dt("主演")
_RE_DT_DIRECTOR = _dt("导演")
_RE_DT_AREA     = _dt("地区")
_RE_DT_YEAR     = _dt("年份")
_RE_DT_STATUS   = _dt("状态")

# 完整剧情正文
_RE_VOD_CONTENT = re.compile(r'<div class="vod-content">([\s\S]*?)</div>', re.I)

# 线路 tab：href="#playurl-tab-6" ... 线路1
_RE_TAB = re.compile(
    r'href="#playurl-tab-(\d+)"[^>]*>[\s\S]*?</span>\s*([^<]+?)\s*</a>', re.I)

# tab 面板：id="playurl-tab-6" ... </ul>
_RE_TABPANE = re.compile(
    r'<div[^>]*id="playurl-tab-(\d+)"[^>]*>([\s\S]*?)</div>', re.I)

# 面板内剧集：href="/playurl/z9696775/6/1.html" title="TC"
_RE_EPISODE = re.compile(
    r'<a[^>]*href="(/playurl/[^"]+?)"[^>]*title="([^"]*)"[^>]*>([^<]*)</a>', re.I)

# 播放页 player_aaaa
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)
_RE_PLAYER_LOOSE = re.compile(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*;', re.I)


class Spider(Spider):

    def getName(self):
        return "泡泡影院"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础 ----------------

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

    def _is_error_page(self, html):
        if not html:
            return True
        low = html.lower()
        if "error code 52" in low or "web server is returning" in low:
            return True
        if "cloudflare" in low and "ray id" in low:
            return True
        return False

    # ---------------- 列表 ----------------

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        if self._is_error_page(html):
            self.log("  站点返回错误页，跳过")
            return videos

        items = _RE_LI.findall(html)
        self.log("  卡片数: %d" % len(items))

        for it in items:
            m = _RE_LINK.search(it)
            if not m:
                continue
            href = m.group(1).replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)

            pic = ""
            mi = _RE_IMG_DATA.search(it)
            if mi:
                pic = self._fix_url(mi.group(1))
            if not pic or pic.endswith("load.gif"):
                ma = _RE_IMG_ANY.search(it)
                if ma and "load.gif" not in ma.group(1):
                    pic = self._fix_url(ma.group(1))
            pic = pic or self.default_pic

            name = ""
            mn = _RE_ALT.search(it)
            if mn:
                name = self._clean(mn.group(1))
            if not name:
                mt = _RE_TITLE_ATTR.search(it)
                if mt:
                    name = self._clean(mt.group(1))
            name = name or href.rsplit("/", 1)[-1].replace(".html", "")

            remarks = ""
            mr = _RE_REMARKS.search(it)
            if mr:
                remarks = self._clean(mr.group(1))

            videos.append({
                "vod_id":      href,
                "vod_name":    name[:100],
                "vod_pic":     pic,
                "vod_remarks": remarks,
            })
        return videos

    def _page_count(self, html, cid):
        """总页数取自真实“尾页”链接：
            分类/频道页  <a href="/class/13-2630.html">尾页</a>
            explore 页   <a href="/explore/.../page/58.html">尾页</a>
        """
        if not html or self._is_error_page(html):
            return 1
        cid = re.escape(str(cid))
        pats = [
            r'href="/class/%s-(\d+)\.html"[^>]*>\s*尾页' % cid,
            r'href="[^"]*/page/(\d+)\.html"[^>]*>\s*尾页',
            r'href="[^"]*page/(\d+)[^"]*"[^>]*>\s*尾页',
        ]
        for p in pats:
            m = re.search(p, html, re.I)
            if m:
                try:
                    return max(1, int(m.group(1)))
                except Exception:
                    pass
        return 1

    # ---------------- TVBox 接口 ----------------

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML: %d" % len(html))
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        tid = str(tid)

        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}

        cat  = (extend.get("cat")  or "").strip()   # 分类ID（国产剧=13）
        area = (extend.get("area") or "").strip()   # 地区
        year = (extend.get("year") or "").strip()   # 年代
        by   = (extend.get("by")   or "").strip()   # 排序

        # 真实路径拼接（严格对应站内链接格式）：
        #   /explore[ /class/{类型} ][ /area/{地区} ] /id/{分类或频道id}
        #           [ /year/{年} ][ /by/{排序} ][ /page/{页} ].html
        # 注意 class（类型）段必须在 id 之前，见真实样本
        #   /explore/class/古装/id/13.html
        if cat or area or year or by:
            cid = cat or tid
            # 真实组合顺序（取自页内真实链接）：
            #   /explore/by/hits/id/13.html              ← by 在最前
            #   /explore/area/内地/id/13.html            ← area 在最前
            #   /explore/area/内地/id/13/year/2018.html  ← area→id→year
            #   /explore/class/古装/id/13.html           ← class 在最前
            # 归纳：by / area → id → year
            seg = []
            if by:
                seg.append("/by/%s" % by)
            if area:
                seg.append("/area/%s" % urllib.parse.quote(area))
            seg.append("/id/%s" % cid)
            if year:
                seg.append("/year/%s" % year)
            # 实测：explore 页自身没有 /page/N 形式，其“下一页/尾页”一律回到
            # /class/{cid}-{N}.html，故翻页直接走 class 路径
            if page > 1:
                url = "%s/class/%s-%d.html" % (self.site_url, cid, page)
            else:
                url = self.site_url + "/explore" + "".join(seg) + ".html"
        else:
            cid = tid
            url = ("%s/class/%s-%d.html" % (self.site_url, cid, page)
                   if page > 1 else "%s/class/%s.html" % (self.site_url, cid))

        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html, cat or tid)
        self.log("  结果: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos) if videos else 24,
            "total": pagecount * (len(videos) if videos else 24),
        }

    def searchContent(self, key, quick, pg="1"):
        kw = urllib.parse.quote(key)
        url = "%s/query.html?wd=%s" % (self.site_url, kw)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos,
            "page": int(pg) if pg else 1,
            "pagecount": 1,
            "limit": len(videos) if videos else 24,
            "total": len(videos),
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 ----------------

    def _dl_value(self, html, regex):
        m = regex.search(html)
        if not m:
            return ""
        return self._clean(m.group(1))

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML: %d" % len(html))
        if not html or self._is_error_page(html):
            self.log("  详情页不可用")
            return {"list": []}

        # 标题：优先 <a class="ff-text">片名</a>，其次 <title>
        name = ""
        m = _RE_D_TITLE.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_H1.search(html)
            if m:
                name = self._clean(m.group(1))
        if not name:
            m = _RE_TAG_TITLE.search(html)
            if m:
                name = self._clean(m.group(1)).split(" - ")[0]
        name = name or vod_id

        # 封面
        pic = ""
        mi = _RE_IMG_DATA.search(html)
        if mi:
            pic = self._fix_url(mi.group(1))
        if not pic or pic.endswith("load.gif"):
            for mm in _RE_IMG_ANY.finditer(html):
                u = self._fix_url(mm.group(1))
                if u and "load.gif" not in u:
                    pic = u
                    break
        pic = pic or self.default_pic

        # 元信息
        actor    = self._dl_value(html, _RE_DT_ACTOR)
        director = self._dl_value(html, _RE_DT_DIRECTOR)
        area     = self._dl_value(html, _RE_DT_AREA)
        year     = self._dl_value(html, _RE_DT_YEAR)
        status   = self._dl_value(html, _RE_DT_STATUS)

        actor = re.sub(r"\s+", ", ", actor).strip(", ") if actor else ""
        actor = actor.replace(", ,", ",")

        # 简介：用完整剧情正文 vod-content（不是带“详细...”截断的 vod-blurb）
        content = ""
        mc = _RE_VOD_CONTENT.search(html)
        if mc:
            content = self._clean(mc.group(1))
        if not content:
            # 兜底：meta description
            md = re.search(r'<meta[^>]*name=["\']description["\'][^>]*'
                           r'content=["\']([^"\']*)["\']', html, re.I)
            if md:
                content = self._clean(md.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 线路 + 剧集：从 tab 的 href="#playurl-tab-{sid}" 取 sid（真实顺序是乱的）
        tab_names = {}
        for m in _RE_TAB.finditer(html):
            sid, label = m.group(1), self._clean(m.group(2))
            if sid not in tab_names:
                tab_names[sid] = label

        groups = []   # [(label, sid, [(ep_name, url), ...])]
        for m in _RE_TABPANE.finditer(html):
            sid, block = m.group(1), m.group(2)
            eps = []
            for em in _RE_EPISODE.finditer(block):
                href, title, text = em.group(1), em.group(2), em.group(3)
                href = href.replace("&amp;", "&")
                ep_name = self._clean(title) or self._clean(text) or \
                          ("第%d集" % (len(eps) + 1))
                eps.append((ep_name, self._fix_url(href)))
            if eps:
                label = tab_names.get(sid) or ("线路%s" % sid)
                groups.append((label, sid, eps))

        self.log("  线路: %s" % [(g[0], g[1], len(g[2])) for g in groups])

        if not groups:
            return {"list": []}

        play_from = "$$$".join(g[0] for g in groups)
        play_url = "$$$".join(
            "#".join("%s$%s" % (n, u) for n, u in g[2]) for g in groups)

        remarks = status or ("%d条线路" % len(groups))

        return {"list": [{
            "vod_id":        vod_id,
            "vod_name":      name,
            "vod_pic":       pic,
            "vod_content":   content,
            "vod_actor":     actor,
            "vod_director":  director,
            "vod_area":      area,
            "vod_year":      year,
            "vod_remarks":   remarks,
            "vod_play_from": play_from,
            "vod_play_url":  play_url,
        }]}

    # ---------------- 播放 ----------------

    def _parse_player(self, html):
        """解析 player_aaaa 的 url 字段（真实为直链 m3u8）"""
        if not html:
            return ""
        m = _RE_PLAYER.search(html) or _RE_PLAYER_LOOSE.search(html)
        if not m:
            return ""
        raw = m.group(1)
        try:
            data = json.loads(raw)
        except Exception:
            mu = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            if mu:
                return mu.group(1).replace("\\/", "/")
            return ""
        u = data.get("url") or ""
        return u.replace("\\/", "/")

    def playerContent(self, flag, id, vipFlags):
        play_url = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_url)

        now = int(time.time())
        if play_url in self._play_cache:
            ts, res = self._play_cache[play_url]
            if now - ts < 600:
                return res

        html = self._fetch(play_url)
        m3u8 = self._parse_player(html)

        if m3u8 and m3u8.startswith("http"):
            self.log("  => 直链: %s" % m3u8[:120])
            res = {
                "parse": 0,
                "playUrl": "",
                "url": m3u8,
                "header": {
                    "User-Agent": UA,
                    "Referer": play_url,
                },
            }
        else:
            self.log("  未取到直链，交给嗅探")
            res = {
                "parse": 1,
                "playUrl": "",
                "url": play_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }

        self._play_cache[play_url] = (now, res)
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
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
