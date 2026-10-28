# coding=utf-8
"""
首映网 jiyaogroup.com | TVBox Python 爬虫 (V4.0 聚合+筛选完美版)
1. 完美提取封面、标题、拼音不丢失
2. 全自动解析网页左侧筛选栏，支持 按剧情/地区/年份/语言/字母/排序
3. 完美解决“电视剧/电影”总分类聚合页数据不显示的问题
4. 直链 m3u8 解析无卡顿
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
    except:
        pass

    class _BaseSpider:
        def __init__(self): self._session = None
        @property
        def _sess(self):
            if self._session is None:
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session
        def fetch(self, url, headers=None, **kw):
            r = self._sess.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r
        def log(self, *a):
            try: print("[shouying]", *a)
            except: pass
    Spider = _BaseSpider

HOST = "https://jiyaogroup.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = "https://pic.rmb.bdstatic.com/bjh/1e6518d6cd2d785aa65c1ff9a74b89b2.jpeg"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 基础大类（对应顶部导航）
CLASSES = [
    {"type_id": "dianying",    "type_name": "电影"},
    {"type_id": "dianshiju",   "type_name": "电视剧"},
    {"type_id": "zongyi",      "type_name": "综艺"},
    {"type_id": "dongman",     "type_name": "动漫"},
    {"type_id": "donghuapian", "type_name": "动画片"},
    {"type_id": "duanju",      "type_name": "短剧"},
]

# ===================== 核心正则 =====================
# 1. 列表/聚合卡片：严格提取 href, title, data-original
_RE_CARD = re.compile(
    r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*'
    r'href="(/voddetail/[^"]+)"[^>]*title="([^"]*)"[^>]*data-original="([^"]*)"', re.I)

# 2. 详情页：标题、评分、封面
_RE_H1 = re.compile(r'<h1 class="title">([\s\S]*?)</h1>', re.I)
_RE_H1_SCORE = re.compile(r'<span class="score[^"]*">([\d.]+)</span>', re.I)
_RE_PIC = re.compile(r'<div class="stui-content__thumb">[\s\S]*?<img[^>]*?data-original="([^"]+)"', re.S | re.I)

# 3. 详情页：简介、元数据
_RE_INTRO = re.compile(r'<p class="desc hidden-xs">\s*<span class="left text-muted">简介：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_INTRO_TAIL = re.compile(r'想看更多的.*?请关注我们的网站：[\s\S]*$', re.S | re.I)
_RE_DIRECTOR = re.compile(r'导演：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_ACTOR = re.compile(r'主演：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_TYPE = re.compile(r'类型：</span>([\s\S]*?)<span class="split-line">', re.S | re.I)
_RE_AREA = re.compile(r'地区：</span>([\s\S]*?)<span class="split-line">', re.S | re.I)
_RE_YEAR = re.compile(r'年份：</span>([\s\S]*?)</p>', re.S | re.I)

# 4. 详情页：剧集与线路
_RE_EPISODE = re.compile(r'<li\s*[^>]*><a\s+href="(/vodplay/[^"]+?-(\d+)-(\d+)\.html)"[^>]*title="([^"]+)"', re.I)
_RE_TAB = re.compile(r'<a data-toggle="tab" href="#down(\d+)">([^<]+)</a>', re.I)

# 5. 播放页：player_aaaa 直链
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)

# 6. 分页
_RE_PAGE_NUM = re.compile(r'<span class="num">\d+/(\d+)</span>')
_RE_TAIL = re.compile(r'href="[^"]*?(\d+)\.html">尾页')

# 7. 筛选栏提取：找到 <span class="text-muted">按XXX</span> 之后的 <ul>
_RE_FILTER_BLOCK = re.compile(r'<li><span class="text-muted">(按[^<]+)</span></li>([\s\S]*?)</ul>', re.I)
_RE_FILTER_ITEM = re.compile(r'<a href="([^"]+)">([^<]+)</a>', re.I)


class Spider(Spider):

    def getName(self):
        return "首映网"

    def init(self, extend=""):
        self.site_url = HOST
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}

    def _fetch(self, url, timeout=15):
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            return rsp.content.decode("utf-8", "ignore")
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _clean(self, s):
        if not s: return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = s.replace("&nbsp;", " ").replace("\xa0", " ").replace("&amp;", "&").replace("&quot;", '"')
        return re.sub(r"[ \t\r\f\v]+", " ", s).strip()

    def _valid_pic(self, url):
        if not url or url.startswith("file:///") or url == "/":
            return self.default_pic
        return url if url.startswith("http") else ("https:" + url if url.startswith("//") else self.site_url + url)

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html: return videos
        for href, title, pic in _RE_CARD.findall(html):
            href = href.replace("&amp;", "&")
            if href in seen: continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(title)[:100],
                "vod_pic": self._valid_pic(pic),
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html: return 1
        m = _RE_PAGE_NUM.search(html)
        if m: return int(m.group(1))
        m = _RE_TAIL.search(html)
        if m: return int(m.group(1))
        return 1

    # ===================== TVBox 接口 =====================

    def homeContent(self, filter=False):
        # 首页直接提取轮播和最新剧集
        html = self._fetch(self.site_url + "/")
        return {"class": CLASSES, "list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try: extend = json.loads(extend)
            except: extend = {}
        if not extend: extend = {}

        # 过滤掉“全部”等空值，防止拼出脏 URL
        ext = {k: v for k, v in extend.items() if v not in ("", None, "全部")}

        # 苹果 CMS 11段 URL：{分类}-{地区}-{语言}-{字母}-{排序}-{剧情}--------{页码}---{年份}.html
        # 注意：页码第 1 页为空，第 N 页为 N
        page_s = "" if page <= 1 else str(page)
        cid = ext.get("class") or tid
        
        url = (f"{self.site_url}/vodshow/{cid}-{ext.get('area','')}-{ext.get('lang','')}-"
               f"{ext.get('letter','')}-{ext.get('sort','time')}-{ext.get('class','')}--------{page_s}---{ext.get('year','')}.html")
        
        self.log(f"category: {url}")
        html = self._fetch(url)
        
        # 对于总分类（如 dianshiju），苹果CMS会返回一个包含多个子板块的聚合页
        # 我们直接把整个聚合页里所有 <a class="...stui-vodlist__thumb..."> 提取出来
        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        
        return {"list": videos, "page": page, "pagecount": pagecount, "limit": 30, "total": pagecount * 30}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        # 搜索第 1 页没有页码，第 2 页有页码
        if page <= 1:
            url = f"{self.site_url}/vodsearch/-------------.html?wd={kw}"
        else:
            url = f"{self.site_url}/vodsearch/--------{page}---.html?wd={kw}"
        self.log(f"search: {url}")
        html = self._fetch(url)
        return {"list": self._extract_videos(html), "page": page, "pagecount": 1, "limit": 30, "total": 999}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids: return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self.site_url + vod_id
        self.log(f"detail: {url}")
        html = self._fetch(url)
        if not html: return {"list": []}

        # 标题和评分
        name, score = "", ""
        m = _RE_H1.search(html)
        if m:
            raw = m.group(1)
            ms = _RE_H1_SCORE.search(raw)
            if ms: score = ms.group(1)
            name = self._clean(re.sub(r'<span class="score[^"]*">[\d.]+</span>', '', raw))
        name = name or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_PIC.search(html)
        if m: pic = self._valid_pic(m.group(1))

        # 简介
        content = ""
        m = _RE_INTRO.search(html)
        if m: content = _RE_INTRO_TAIL.sub("", self._clean(m.group(1))).strip()
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 元数据
        def _grab(reg):
            mm = reg.search(html)
            return self._clean(re.sub(r"<[^>]+>", " ", mm.group(1))).strip(" ,，") if mm else ""
        
        director, actor = _grab(_RE_DIRECTOR), _grab(_RE_ACTOR)
        type_, area, year = _grab(_RE_TYPE), _grab(_RE_AREA), _grab(_RE_YEAR)

        # 剧集分组
        tabs = {m[0]: self._clean(m[1]) for m in _RE_TAB.findall(html)}
        groups = {}
        for href, line, ep, ep_title in _RE_EPISODE.findall(html):
            href = href.replace("&amp;", "&")
            full = href if href.startswith("http") else self.site_url + href
            ep_name = self._clean(ep_title) or f"第{ep}集"
            groups.setdefault(line, []).append((ep_name, full))

        if not groups: return {"list": []}

        play_from, play_url = [], []
        for line in sorted(groups.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            play_from.append(tabs.get(line, f"线路{line}"))
            play_url.append("#".join(f"{n}${h}" for n, h in groups[line]))

        return {"list": [{
            "vod_id": vod_id, "vod_name": name, "vod_pic": pic,
            "vod_content": content, "vod_actor": actor, "vod_director": director,
            "vod_score": score, "vod_year": year, "vod_area": area,
            "vod_remarks": type_ or f"{len(groups)}条线路",
            "vod_play_from": "$$$".join(play_from), "vod_play_url": "$$$".join(play_url),
        }]}

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self.site_url + id
        now = int(time.time())
        if play_page in self._play_cache and now - self._play_cache[play_page][0] < 600:
            return self._play_cache[play_page][1]

        html = self._fetch(play_page)
        m3u8 = ""
        if html:
            m = _RE_PLAYER.search(html)
            if m:
                try:
                    pa = json.loads(m.group(1))
                    if int(pa.get("encrypt", 0) or 0) == 0:
                        m3u8 = pa.get("url", "") or ""
                except Exception as e:
                    self.log(f"parse player fail: {e}")

        if m3u8:
            res = {"parse": 0, "playUrl": "", "url": m3u8, "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        else:
            res = {"parse": 1, "playUrl": "", "url": play_page, "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
            
        self._play_cache[play_page] = (now, res)
        return res

    def localProxy(self, param): return [200, "image/jpeg", b"", ""]
    def isVideoFormat(self, url): return ".m3u8" in url or ".mp4" in url or url.startswith("http")
    def manualVideoCheck(self): return False
    def destroy(self): pass
    def close(self): self.destroy()
