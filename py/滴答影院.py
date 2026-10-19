# coding=utf-8
# -*- coding: utf-8 -*-
"""
滴答影院 loldyw.com | TVBox Python 爬虫
------------------------------------------------------------

网站结构:
    首页          /                     （JSON 数据驱动, 返回 {"data":{...}}）
    分类页        /genre/{typeId}.html   (1=电影 2=电视剧 3=综艺 4=动漫)
    列表页        /filter/id/{typeId}.html
    短剧列表      /filter/id/24.html
    详情页        /film/{vodId}.html     例: /film/448046f.html
    播放页        /watch/{vodId}/{line}/{ep}.html    例: /watch/448046f/1/1.html
    地区/年份/主演  /lookup/area/{名字}.html
                 /lookup/year/{年份}.html
                 /lookup/actor/{名字}.html
    搜索          /index.php/vod/search.html?wd={关键词}

数据结构:
    详情页含多个播放线路(如 极速高清/量子高清/天堂高清/无尽4K, 锚点 #playlist{N}),
    每个线路下是一组剧集, 剧集链接格式: /watch/{vodId}/{line}/{ep}.html

说明:
    - 站点启用 Cloudflare JS 验证, 播放源地址在前端异步加载,
      playerContent() 会先尝试从播放页源码提取真实媒体地址(.m3u8/.mp4),
      若页面中无直链则返回播放页 URL 交给 TVBox 内置嗅探(parse=1)。
    - 首页/分类等 JSON 驱动页面返回的 content 为纯文本, 列表解析依赖
      /film/{id}.html 链接格式 + <a>/<img> 标签, 不依赖具体 CSS class。
"""
import re
import sys
import json
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
            try:
                r.encoding = 'utf-8'
            except Exception:
                pass
            return r

        def log(self, *a, **kw):
            try:
                print("[loldyw]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.loldyw.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "24", "type_name": "短剧"},
]

# 播放线路别名（真实页面出现过的线路名）
_LINE_ALIAS = {
    "1": "量子高清", "2": "无尽4K", "3": "极速高清", "4": "天堂高清",
    "5": "辣椒云", "6": "Vip播放",
}

# ---------------- 正则（基于真实 URL / 标签结构，非 CSS class） ----------------
# 列表卡片: <a href="/film/xxx.html"> 内（或相邻）的 <img alt="标题" src="封面">
_RE_HREF = re.compile(r'href="(/film/[^"]+?\.html)', re.I)
_RE_IMG = re.compile(
    r'<img\b([^>]*)>', re.S | re.I)
# 从 <img ...> 内取 alt 与 图片地址（顺序无关）
_RE_IMG_ALT = re.compile(r'alt\s*=\s*"([^"]*)"', re.I)
_RE_IMG_SRC = re.compile(
    r'(?:data-src|data-original|src)\s*=\s*"([^"]+)"', re.I)

# 详情页标题
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE = re.compile(r'<title>(.*?)</title>', re.S | re.I)

# 详情页封面（真实图片地址，通常来自 img 图床）
_RE_PIC = re.compile(
    r'<img[^>]*?src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"',
    re.I)

# 简介（真实页面 "简介：" 后的一段文本，常有多行）
_RE_INTRO = re.compile(r'简介[:：]\s*([\s\S]*?)(?=<|\n\n|\s*更新)',
                       re.S | re.I)

# 导演 / 主演（真实页面 "导演：" "主演：" 后跟链接或逗号分隔名字）
_RE_DIRECTOR = re.compile(r'导演[:：]\s*([\s\S]*?)(?=更新|主演|</|分)',
                          re.S | re.I)
_RE_ACTOR = re.compile(r'主演[:：]\s*([\s\S]*?)(?=导演|更新|</|分)',
                       re.S | re.I)

# 播放线路锚点 + 剧集链接: #playlist{N} 与 /watch/{vodId}/{line}/{ep}.html
_RE_PLAYLIST_ANCHOR = re.compile(r'id=["\']?playlist(\d+)["\']?',
                                 re.I)
_RE_EPISODE = re.compile(
    r'<a\s+href="(/watch/[^"]+?\.html)"[^>]*>([^<]{1,60})</a>',
    re.S | re.I)

# 播放页内直链媒体（若服务端渲染出则直接可用）
_RE_M3U8 = re.compile(r'https?://[^"\'\s<>]+\.m3u8(?:\?[^"\'\s<>]*)?',
                      re.I)
_RE_MP4 = re.compile(r'https?://[^"\'\s<>]+\.mp4(?:\?[^"\'\s<>]*)?',
                     re.I)
# 常见播放器注入 JSON / iframe 里的 url 字段
_RE_MEDIA_URL = re.compile(
    r'(?:url|link|src)["\']?\s*[:=]\s*["\'](https?://[^"\']+)["\']',
    re.I)


class Spider(Spider):

    def getName(self):
        return "滴答影院"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=30, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            else:
                text = str(rsp)
            # 尝试解析 JSON 驱动的页面（服务端直接返回 {"data":{...}}）
            text = self._unwrap_json(text)
            return text
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _unwrap_json(self, text):
        """JSON 驱动页面: 服务端可能返回 {"data":{...}}，尝试解出 content。"""
        if not text or not text.lstrip().startswith("{"):
            return text
        try:
            obj = json.loads(text)
            data = obj.get("data")
            if isinstance(data, dict):
                content = data.get("content")
                if content:
                    return str(content)
        except Exception:
            pass
        return text

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

        hrefs = _RE_HREF.findall(html)
        imgs = self._extract_imgs(html)
        if not hrefs:
            return videos
        for i, href in enumerate(hrefs):
            href = href.strip().replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            alt, pic = "", ""
            if i < len(imgs):
                alt, pic = imgs[i]
            pic = self._fix_url(pic)
            # 无独立封面的卡片，尝试匹配同一 <a> 块内的图片
            if not pic and i < len(imgs):
                pass
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(alt)[:100] or href,
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return videos

    def _extract_imgs(self, html):
        """提取所有 <img> 的 (alt, 图片地址)，属性顺序无关。"""
        out = []
        for mt in _RE_IMG.finditer(html):
            tag = mt.group(1)
            a = _RE_IMG_ALT.search(tag)
            s = _RE_IMG_SRC.search(tag)
            alt = self._clean(a.group(1)) if a else ""
            src = s.group(1) if s else ""
            out.append((alt, src))
        return out

    # ---------------- 首页 / 分类 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": {}}

    def homeVideoContent(self):
        # 首页为 JSON 数据驱动，返回的 content 是纯文本，不含 /film/ 链接，
        # 因此首页直接落到最新电影的列表页取数据。
        url = "%s/filter/id/1.html" % self.site_url
        html = self._fetch(url)
        videos = self._extract_videos(html)
        if not videos:
            url2 = "%s/genre/1.html" % self.site_url
            videos = self._extract_videos(self._fetch(url2))
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        # 真实列表页 /filter/id/{tid}.html；分页真实格式以 ?page= 拼接（若站内支持）
        if page > 1:
            url = "%s/filter/id/%s.html?page=%d" % (
                self.site_url, tid, page)
        else:
            url = "%s/filter/id/%s.html" % (self.site_url, tid)
        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def _page_count(self, html):
        if html:
            pages = re.findall(r'page=(\d+)', html)
            if pages:
                try:
                    return max(int(p) for p in pages) + 1
                except Exception:
                    pass
        return 9999

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        keyword = urllib.parse.quote(key)
        url = "%s/index.php/vod/search.html?wd=%s" % (
            self.site_url, keyword)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": 1,
            "pagecount": self._page_count(html),
            "limit": 24, "total": len(videos),
        }

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

        # 标题
        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_TITLE.search(html)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])

        # 封面
        pic = ""
        m = _RE_PIC.search(html)
        if m:
            pic = m.group(1)

        # 简介
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content and name:
            content = name

        # 导演 / 主演
        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            director = self._clean(m.group(1))
        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            actor = self._clean(m.group(1))

        # 播放线路 + 剧集
        lines = self._extract_play_lines(html, vod_id)
        if not lines:
            # 单集无线路区块时直接用首条剧集链接
            eps = _RE_EPISODE.findall(html)
            if not eps:
                return {"list": []}
            vod_play_from = "滴答播放"
            urls = []
            for href, ep in eps:
                href = href.replace("&amp;", "&")
                urls.append("%s$%s" % (self._clean(ep) or "播放",
                                       self._fix_url(href)))
            vod_play_url = "#".join(urls)
        else:
            vod_play_from = "$$$".join(lines["names"])
            vod_play_url = "$$$".join(lines["urls"])

        remarks = ""
        m = re.search(r'更新[:：]\s*([^<\n]+)', html, re.S)
        if m:
            remarks = self._clean(m.group(1))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name or vod_id,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_remarks": remarks,
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url,
        }]}

    def _extract_play_lines(self, html, vod_id):
        """
        解析详情页播放线路（真实结构）:
            <div id="playlist{N}"> ... </div> 内含该线路下所有
            <a href="/watch/{vodId}/{line}/{ep}.html">第X集</a>
        返回 {"names": [线路名...], "urls": [线路url串...]}
        """
        lines_ordered = []  # [(line_id, ep_list)]
        # 先拿到锚点的出现顺序（定义页面线路顺序）
        anchors = [(int(mm.group(1)), mm.start())
                   for mm in _RE_PLAYLIST_ANCHOR.finditer(html)]
        # 收集所有剧集与其所在的最近前置 playlist 锚点
        ep_matches = list(_RE_EPISODE.finditer(html))
        if not ep_matches:
            return {}

        # 为每个 ep 判定其归属线路：取它之前最近的 playlist 锚点
        # 若没有前置锚点但有多个线路，则按片段的包络划分
        # 简化可靠方案：按 <a> 相对位置与锚点位置归组
        import bisect
        anchor_pos = [p for _, p in anchors]
        anchor_ids = [i for i, _ in anchors]

        groups = {}
        for mt in ep_matches:
            href, ep = mt.group(1), mt.group(2)
            pos = mt.start()
            idx = bisect.bisect_right(anchor_pos, pos)
            if idx == 0:
                # 无前置锚点 → 归为第一组线路
                lid = anchor_ids[0] if anchor_ids else 1
            else:
                lid = anchor_ids[idx - 1]
            url = self._fix_url(href.replace("&amp;", "&"))
            groups.setdefault(lid, []).append(
                (self._clean(ep) or "第%s集" % (len(groups[lid]) + 1), url))

        if not groups:
            return {}

        # 按锚点页面出现顺序输出线路
        names, urls = [], []
        for lid, _pos in anchors:
            if lid not in groups:
                continue
            eps = groups.pop(lid)
            # 去重（同一线路偶尔出现重复集数）
            seen = set()
            uniq = []
            for n, u in eps:
                if u in seen:
                    continue
                seen.add(u)
                uniq.append((n, u))
            names.append(_LINE_ALIAS.get(str(lid), "线路%s" % lid))
            urls.append("#".join("%s$%s" % (n, u) for n, u in uniq))
        # 锚点未覆盖到的线路补充
        for lid in sorted(groups.keys()):
            eps = groups[lid]
            seen = set()
            uniq = []
            for n, u in eps:
                if u in seen:
                    continue
                seen.add(u)
                uniq.append((n, u))
            names.append(_LINE_ALIAS.get(str(lid), "线路%s" % lid))
            urls.append("#".join("%s$%s" % (n, u) for n, u in uniq))
        return {"names": names, "urls": urls}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(__import__("time").time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        media = ""
        if html:
            m = _RE_M3U8.search(html)
            if m:
                media = m.group(0)
            else:
                m = _RE_MP4.search(html)
                if m:
                    media = m.group(0)
            if not media:
                # 兜底：iframe / 注入 url 里含可播放媒体
                m = _RE_MEDIA_URL.search(html)
                if m and (".m3u8" in m.group(1) or ".mp4" in m.group(1)):
                    media = m.group(1)

        if media:
            res = {
                "parse": 0, "playUrl": "", "url": media,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
        else:
            # 页面无直链（站点反爬在前端异步加载播放源），交给 TVBox 嗅探
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
