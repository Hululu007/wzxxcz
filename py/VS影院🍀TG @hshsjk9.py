# coding=utf-8
"""
VS影院 vssdy.com | TVBox Python 爬虫 
- 列表/搜索/分类：正则通吃
- 详情：h1 + data-original + #desc + 线路 tabs + 剧集 UL
- 播放：parse:1 交给 TVBox 嗅探（getPlay 在 dypck.js，异步 ajax + XOR 解密）
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
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[vssdy]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.vssdy.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/dydysf/yj_pic/img/load.jpg"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "电影",   "type_name": "电影"},
    {"type_id": "电视剧", "type_name": "电视剧"},
    {"type_id": "综艺",   "type_name": "综艺"},
    {"type_id": "动漫",   "type_name": "动漫"},
    {"type_id": "短剧",   "type_name": "短剧"},
]

# ===================== 列表正则 =====================
_RE_CARD = re.compile(
    r'<a\s+class="[^"]*stui-vodlist__thumb lazyload[^"]*"\s+'
    r'href="(/resource/\d+\.html)"\s+'
    r'title="([^"]*)"\s+'
    r'data-original="([^"]*)"[^>]*>'
    r'[\s\S]{0,300}?'
    r'<span class="pic-text text-right">([^<]*)</span>',
    re.S | re.I)

_RE_TEXT_CARD = re.compile(
    r'<a class="top-line-dot text-overflow" href="(/resource/\d+\.html)" title="([^"]*)">\s*'
    r'<span class="text-muted pull-right">([^<]*)</span>([^<]*)</a>',
    re.S | re.I)

_RE_PAGE = re.compile(r'page=(\d+)', re.I)

# ===================== 详情正则 =====================
_RE_H1 = re.compile(r'<h1 class="title">([^<]+)</h1>', re.I)
_RE_DETAIL_PIC = re.compile(
    r'<div class="stui-content__thumb">[\s\S]*?<img[^>]*data-original="([^"]+)"',
    re.I)
_RE_DETAIL_REMARK = re.compile(
    r'<div class="stui-content__thumb">[\s\S]*?<span class="pic-text text-right">([^<]*)</span>',
    re.I)
_RE_INTRO_FULL = re.compile(
    r'<div[^>]*id="desc"[^>]*>[\s\S]*?<div class="col-pd">([\s\S]*?)</div>',
    re.I)
_RE_ACTOR = re.compile(
    r'<span class="text-muted">主演：</span>\s*([\s\S]*?)</p>', re.I)
_RE_DIRECTOR = re.compile(
    r'<span class="text-muted">导演：</span>\s*([\s\S]*?)</p>', re.I)

# ===================== 线路/剧集正则 =====================
_RE_LINE_TABS = re.compile(
    r'<a href="javascript:;" data-target="\.ff-playurl-tab-(\d+)" data-toggle="tab">\s*'
    r'<span[^>]*></span>([^<]+)</a>',
    re.S | re.I)
_RE_EPISODE_UL = re.compile(
    r'<ul class="stui-content__playlist[^"]*ff-playurl-tab-(\d+)[^"]*">([\s\S]*?)</ul>',
    re.S | re.I)
_RE_EPISODE_A = re.compile(
    r'<a title="([^"]*)" href="(/play/[^"]+)" target="_self">([^<]*)</a>',
    re.S | re.I)

# ===================== 播放直链（尽力版）正则 =====================
_RE_PLAY_PATH = re.compile(r'/play/(\d+)-(\d+)-(\d+)\.html', re.I)


class Spider(Spider):

    def getName(self):
        return "VS影院"

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
        self.log("init: site=%s" % self.site_url)

    # ---------- 工具 ----------
    def _fetch(self, url, timeout=20):
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=timeout)
            return rsp.text or ""
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

    # ---------- 列表 ----------
    def _extract_videos(self, html):
        videos, seen = [], set()
        if not html:
            return videos

        for href, title, pic, remark in _RE_CARD.findall(html):
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(title)[:100],
                "vod_pic":     pic or self.default_pic,
                "vod_remarks": self._clean(remark),
            })

        for href, title, remark, name in _RE_TEXT_CARD.findall(html):
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(title or name)[:100],
                "vod_pic":     self.default_pic,
                "vod_remarks": self._clean(remark),
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = _RE_PAGE.findall(html)
        if pages:
            try:
                return max(int(p) for p in pages) + 1
            except Exception:
                pass
        return 9999

    def homeContent(self, filter=False):
        return {"class": CLASSES}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML: %d" % len(html))
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        area = ""
        year = ""
        if isinstance(extend, dict):
            area = extend.get("area", "") or ""
            year = extend.get("year", "") or ""
            if area == "全部":
                area = ""
            if year == "全部":
                year = ""

        cls_enc = urllib.parse.quote(tid)
        area_enc = urllib.parse.quote(area) if area else ""
        year_enc = urllib.parse.quote(year) if year else ""

        path = "/catalog/%s-%s-%s------%d-24.html" % (
            cls_enc, area_enc, year_enc, page - 1)
        url = self.site_url + path + "?order=&page=%d&size=24" % (page - 1)
        self.log("category: %s" % url)

        html = self._fetch(url)
        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  -> %d 条, 总页 %d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        url = "%s/search?searchword=%s&page=%d" % (
            self.site_url, urllib.parse.quote(key), page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 24, "total": 999,
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
        self.log("  HTML: %d" % len(html))
        if not html:
            return {"list": []}

        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>《([^》]+)》", html)
            if m:
                name = self._clean(m.group(1))
        if not name:
            name = vod_id

        pic = self.default_pic
        m = _RE_DETAIL_PIC.search(html)
        if m:
            pic = m.group(1)

        content = ""
        m = _RE_INTRO_FULL.search(html)
        if m:
            content = self._clean(m.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            actor = self._clean(m.group(1))

        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            director = self._clean(m.group(1))

        remark = ""
        m = _RE_DETAIL_REMARK.search(html)
        if m:
            remark = self._clean(m.group(1))

        lines = {}
        for m in _RE_LINE_TABS.finditer(html):
            n = int(m.group(1))
            lines[n] = [self._clean(m.group(2)), []]

        for m in _RE_EPISODE_UL.finditer(html):
            n = int(m.group(1))
            if n not in lines:
                continue
            for a in _RE_EPISODE_A.finditer(m.group(2)):
                ep_name = self._clean(a.group(1))
                ep_url = a.group(2)
                lines[n][1].append((ep_name, ep_url))

        self.log("  线路: %s" % {n: (lines[n][0], len(lines[n][1])) for n in lines})

        play_from, play_url = [], []
        for n in sorted(lines.keys()):
            line_name, eps = lines[n]
            if not eps:
                continue
            play_from.append(line_name)
            play_url.append("#".join("%s$%s" % (ep, u) for ep, u in eps))

        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id":        vod_id,
            "vod_name":      name,
            "vod_pic":       pic,
            "vod_content":   content,
            "vod_actor":     actor,
            "vod_director":  director,
            "vod_remarks":   remark or ("%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        # 优先：尝试直链（尽力版）
        if self.extend.get("direct"):
            direct = self._try_direct_m3u8(play_page)
            if direct:
                self.log("  => direct m3u8: %s" % direct[:160])
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": direct,
                    "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
                }

        # 兜底：交给 TVBox 嗅探
        self.log("  => parse:1 交给 TVBox 嗅探")
        return {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }

    # ---------- 直链（尽力版，可能因算法变动失效） ----------
    def _try_direct_m3u8(self, play_page):
        """
        复现 dypck.js 的 getPlay 逻辑：
          1. 请求 /gpyj/{vid}&pid={line}&url={line}-{ep}&t={ts}&key={calc}
          2. 拿到 hex 响应，XOR 解密
          3. 返回最终 m3u8
        任何一步算法变动都会失败，失败时返回 "" 由 parse:1 兜底。
        """
        m = _RE_PLAY_PATH.search(play_page)
        if not m:
            return ""
        vid, line_idx, ep_idx = m.group(1), int(m.group(2)), int(m.group(3))

        ts = int(time.time())
        # key 算法（基于 dypck.js 反混淆）
        key = ((ts * (ts % 0x10) % 0x5fb) +
               (ts * (ts % 0x20)) +
               0x3020d +
               ts * (ts % 0x40))

        url = "%s/gpyj/%s&pid=%d&url=%d-%d&t=%d&key=%d" % (
            self.site_url, vid, line_idx, line_idx, ep_idx, ts, key)
        self.log("  direct request: %s" % url)

        try:
            rsp = self.fetch(url, headers={
                "User-Agent": UA,
                "Referer": play_page,
                "X-Requested-With": "XMLHttpRequest",
            }, timeout=15)
            raw = (rsp.text or "").strip()
        except Exception as e:
            self.log("  direct fetch fail: %s" % e)
            return ""

        if not raw or len(raw) % 2 != 0:
            self.log("  direct raw 异常: %r" % raw[:60])
            return ""

        # XOR 解密
        try:
            half = len(raw) // 2
            out = []
            for i in range(0, len(raw), 2):
                b = int(raw[i:i + 2], 16)
                b = (b ^ 0x100000) - 0x367 - (half - 1) * (i // 2)
                b = b % 256
                out.insert(0, chr(b))
            final_url = "".join(out)
        except Exception as e:
            self.log("  direct decode fail: %s" % e)
            return ""

        if not final_url.startswith("http"):
            self.log("  direct 结果非 http: %r" % final_url[:80])
            return ""
        if ".m3u8" not in final_url.lower() and ".mp4" not in final_url.lower():
            self.log("  direct 结果非视频: %r" % final_url[:80])
            return ""

        return final_url

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
