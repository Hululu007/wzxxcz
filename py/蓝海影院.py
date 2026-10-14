# coding=utf-8
"""
蓝海影院 desouk.net | TVBox Python 爬虫
架构: 苹果CMS V10 (maccms) + m4-red 模板
关键:
  - 分类: /tv/{id}.html, 分页 /tv/{id}/page/{n}.html
  - 筛选: /tv/{id}[/class/{v}][/area/{v}][/year/{v}][/by/{v}][/page/{n}].html
  - 详情: /video/{id}.html
  - 播放: /play/{id}/{sid}/{nid}.html, player_aaaa.url 即 m3u8 直链
  - 搜索: /search.html?wd={kw}
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
                print("[desouk]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.desouk.net"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/m4-red/img/favicon.ico"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 顶级分类
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "短剧"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "5",  "type_name": "综艺"},
    {"type_id": "48", "type_name": "网飞新剧"},
    {"type_id": "47", "type_name": "AI漫剧"},
]

# 子分类（从真实源码提取）
_SUB_CLASS = {
    "1":  [("6", "剧情片"), ("7", "动作片"), ("8", "冒险片"), ("9", "喜剧片"),
           ("10", "奇幻片"), ("11", "恐怖片"), ("16", "悬疑片"), ("17", "惊悚片"),
           ("18", "灾难片"), ("19", "爱情片"), ("20", "犯罪片"), ("21", "科幻片"),
           ("22", "动画电影"), ("28", "战争片"), ("29", "经典片")],
    "2":  [("12", "国产剧"), ("13", "港剧"), ("14", "韩剧"), ("15", "日剧"),
           ("23", "泰剧"), ("24", "台剧"), ("25", "欧美剧"), ("26", "新马剧"),
           ("27", "纪录片")],
    "3":  [("35", "总裁短剧"), ("36", "神豪短剧"), ("37", "穿越重生短剧"),
           ("38", "都市短剧"), ("39", "年代短剧"), ("40", "长篇剧场")],
    "4":  [("41", "国产动漫"), ("42", "日本动漫"), ("43", "韩国动漫"),
           ("44", "欧美动漫"), ("45", "港台动漫"), ("46", "AI漫剧")],
    "5":  [("49", "国产综艺"), ("50", "港台综艺"), ("51", "韩国综艺"),
           ("52", "日本综艺"), ("53", "欧美综艺")],
    "48": [("54", "网飞电影"), ("55", "网飞自制剧")],
    "47": [("47", "AI漫剧")],
}

# 排序：默认 "" 表示"按时间"，不拼 /by/ 路径
_SORTS = [{"n": "按时间", "v": ""},
          {"n": "按人气", "v": "hits"},
          {"n": "按评分", "v": "score"}]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2011, -1)]

_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
    {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"},
    {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"},
    {"n": "欧美", "v": "欧美"}, {"n": "英国", "v": "英国"},
    {"n": "法国", "v": "法国"}, {"n": "泰国", "v": "泰国"},
    {"n": "印度", "v": "印度"}, {"n": "加拿大", "v": "加拿大"},
    {"n": "西班牙", "v": "西班牙"}, {"n": "德国", "v": "德国"},
    {"n": "俄罗斯", "v": "俄罗斯"}, {"n": "新加坡", "v": "新加坡"},
]

# 每个顶级分类的筛选面板
FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    sub = [{"n": "全部", "v": ""}] + \
          [{"n": n, "v": sid} for sid, n in _SUB_CLASS.get(tid, [])]
    FILTERS[tid] = [
        {"key": "class", "name": "分类", "value": sub},
        {"key": "area",  "name": "地区", "value": _AREAS},
        {"key": "year",  "name": "年份", "value": _YEARS},
        {"key": "by",    "name": "排序", "value": _SORTS},
    ]


# ===================== 正则 =====================

# 每个影片卡片 <li>：用 <li> 分块，防止跨条目匹配
_RE_LI_BLOCK = re.compile(r'<li[^>]*>([\s\S]*?)</li>', re.I)

# 卡片内的 <a class="moive-vodlist__thumb" href="/video/xxx.html" title="片名" data-original="图片">
# 属性顺序不固定，所以用独立的三个正则提取
_RE_A_HREF = re.compile(r'href="(/video/[^"]+?\.html)"', re.I)
_RE_A_TITLE = re.compile(r'title="([^"]*)"', re.I)
_RE_A_PIC = re.compile(r'data-original="([^"]*)"', re.I)
_RE_A_THUMB = re.compile(
    r'<a[^>]*class="[^"]*moive-vodlist__thumb[^"]*"[^>]*>', re.I)

# 播放状态
_RE_PIC_TEXT = re.compile(
    r'<span[^>]*class="pic-text[^"]*"[^>]*>([^<]*)</span>', re.I)

# 详情页信息
_RE_H1 = re.compile(r'<h1[^>]*class="title"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE_TAG = re.compile(r'<title>(.*?)</title>', re.S | re.I)
_RE_OG_IMG = re.compile(
    r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', re.I)
_RE_SCORE = re.compile(
    r'<span[^>]*class="branch"[^>]*>([\d.]+)</span>', re.I)
_RE_ACTOR = re.compile(
    r'<p[^>]*class="data"[^>]*>\s*<span[^>]*class="text-muted"[^>]*>主演：</span>([\s\S]*?)</p>',
    re.S | re.I)
_RE_DIRECTOR = re.compile(
    r'<p[^>]*class="data"[^>]*>\s*<span[^>]*class="text-muted"[^>]*>导演：</span>([\s\S]*?)</p>',
    re.S | re.I)
_RE_STATUS = re.compile(
    r'<p[^>]*class="data"[^>]*>\s*<span[^>]*class="text-muted"[^>]*>状态：</span>([\s\S]*?)</p>',
    re.S | re.I)
_RE_DESC = re.compile(
    r'<div[^>]*class="[^"]*moive-pannel_bd[^"]*"[^>]*>[\s\S]*?<p[^>]*class="col-pd"[^>]*>([\s\S]*?)</p>',
    re.S | re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)

# 播放线路区块：<h3 class="title">...线路X...</h3> ... <ul class="moive-content__playlist clearfix">
_RE_PLAYLIST_BLOCK = re.compile(
    r'<h3[^>]*class="title"[^>]*>[\s\S]*?'
    r'(线路[0-9]+)[\s\S]*?</h3>[\s\S]*?'
    r'<ul[^>]*class="moive-content__playlist[^"]*"[^>]*>([\s\S]*?)</ul>',
    re.S | re.I)

# 剧集条目
_RE_EP = re.compile(
    r'<li[^>]*>\s*<a[^>]*href="(/play/[^"]+\.html)"[^>]*>([^<]+)</a>',
    re.S | re.I)

# player_aaaa
_RE_PLAYER = re.compile(
    r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.S)

# 分页信息
_RE_PAGE_INFO = re.compile(
    r'<span[^>]*class="num"[^>]*>\s*\d+\s*/\s*(\d+)\s*</span>', re.I)
_RE_PAGE_TAIL = re.compile(
    r'href="/tv/[^"]*?/page/(\d+)\.html"[^>]*>\s*尾页', re.I)


class Spider(Spider):

    def getName(self):
        return "蓝海影院"

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
        从分类页/搜索页/详情页提取影片卡片。
        核心思路：先按 <li>...</li> 切块，每块内部再提取 <a class="moive-vodlist__thumb"> 的信息，
        避免跨条目匹配。
        """
        videos = []
        seen = set()
        if not html:
            return videos

        # 方法1: 按 li 分块（分类页/搜索页/详情页的推荐）
        for li_m in _RE_LI_BLOCK.finditer(html):
            block = li_m.group(1)

            # 必须有 moive-vodlist__thumb 的 a 标签
            a_m = _RE_A_THUMB.search(block)
            if not a_m:
                continue
            a_tag = a_m.group(0)

            href_m = _RE_A_HREF.search(a_tag)
            title_m = _RE_A_TITLE.search(a_tag)
            pic_m = _RE_A_PIC.search(a_tag)
            if not href_m:
                continue

            href = href_m.group(1).replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)

            title = title_m.group(1) if title_m else ""
            pic = pic_m.group(1) if pic_m else ""

            # 备注：从 block 里找 pic-text
            remarks = ""
            pt_m = _RE_PIC_TEXT.search(block)
            if pt_m:
                remarks = self._clean(pt_m.group(1))

            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(title)[:100] or href,
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks,
            })

        return videos

    def _page_count(self, html):
        """从分类页提取总页数"""
        if not html:
            return 1
        # 优先取 "1/1348" 这种
        m = _RE_PAGE_INFO.search(html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        # 退化：尾页链接
        m = _RE_PAGE_TAIL.search(html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        # 再退化：找最大的 page 数字
        pages = [int(x) for x in re.findall(r'/page/(\d+)', html)]
        if pages:
            return max(pages)
        return 1

    # ---------------- 首页 / 分类 / 搜索 ----------------

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

        # 清理空值（含中文"全部"）
        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        cid = extend.pop("class", "") or tid
        area = extend.pop("area", "")
        year = extend.pop("year", "")
        by = extend.pop("by", "")

        # 中文排序值 -> 英文；默认"按时间"不拼路径
        by_map = {
            "按时间": "", "按人气": "hits", "按评分": "score",
            "time": "", "hits": "hits", "score": "score",
        }
        by = by_map.get(by, by)

        # 拼路径: /tv/{cid}[/class/{class}][/area/{area}][/year/{year}][/by/{by}][/page/{n}].html
        # 注意：这里的 class 是"剧情"分类（中文），与上面 cid 的"分类"不同。
        # 真实源码里"剧情"分类的链接是 /tv/2/class/喜剧.html，
        # 所以如果 extend 里有 class 且不是数字，就是"剧情"。
        path = "/tv/%s" % cid
        # 注意：extend["class"] 已被 pop 出去并用作 cid 了，
        # 但是如果有"剧情"分类，需要用另一个字段（一般 TVBox 不会传）。
        if area:
            path += "/area/" + urllib.parse.quote(area)
        if year:
            path += "/year/" + year
        if by:
            path += "/by/" + by
        if page and page > 1:
            path += "/page/%d" % page
        path += ".html"

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
        url = "%s/search.html?wd=%s" % (self.site_url, urllib.parse.quote(key))
        if page > 1:
            url += "&page=%d" % page
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        self.log("  got %d videos" % len(videos))
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

        # 标题
        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_TITLE_TAG.search(html)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = name.strip() or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_OG_IMG.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        # 简介
        content = ""
        m = _RE_DESC.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        content = INTRO_PREFIX + "\n" + content if content else INTRO_PREFIX

        # 元信息
        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            actor = re.sub(r"\s*,\s*", ", ", self._clean(m.group(1)))

        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            director = re.sub(r"\s*,\s*", ", ", self._clean(m.group(1)))

        remarks = ""
        m = _RE_STATUS.search(html)
        if m:
            remarks = self._clean(m.group(1))

        # 播放线路
        play_from = []
        play_url = []

        for m in _RE_PLAYLIST_BLOCK.finditer(html):
            line_name = m.group(1).strip()      # "线路1"
            block = m.group(2)
            eps = []
            for em in _RE_EP.finditer(block):
                ep_url, ep_name = em.group(1), em.group(2).strip()
                if not ep_url.startswith("http"):
                    ep_url = self.site_url + ep_url
                eps.append((ep_name, ep_url))
            if eps:
                play_from.append(line_name)
                play_url.append("#".join("%s$%s" % (n, u) for n, u in eps))

        # 去重线路
        seen_lines = set()
        final_from, final_url = [], []
        for f, u in zip(play_from, play_url):
            if f in seen_lines:
                continue
            seen_lines.add(f)
            final_from.append(f)
            final_url.append(u)

        if not final_from:
            self.log("  no play lines found")
            return {"list": []}

        self.log("  lines=%s" % final_from)

        return {"list": [{
            "vod_id":       vod_id,
            "vod_name":     name,
            "vod_pic":      pic,
            "vod_content":  content,
            "vod_actor":    actor,
            "vod_director": director,
            "vod_score":    score,
            "vod_remarks":  remarks or ("%d条线路" % len(final_from)),
            "vod_play_from": "$$$".join(final_from),
            "vod_play_url":  "$$$".join(final_url),
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
            m = _RE_PLAYER.search(html)
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
            self.log("  => m3u8: %s" % m3u8[:160])
            return res

        # 兜底：交给 TVBox
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
