# coding=utf-8
"""
首映网 jiyaogroup.com | TVBox Python 爬虫 (V9.0 斩首行动版)
彻底解决：大类聚合页解析为空、漏斗图标无数据、正则被换行截断的问题。
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
                adapter = _rq.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session
        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r
        def log(self, *a, **kw):
            try: print("[shouying]", *a)
            except: pass
    Spider = _BaseSpider

HOST = "https://jiyaogroup.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = "https://pic.rmb.bdstatic.com/bjh/1e6518d6cd2d785aa65c1ff9a74b89b2.jpeg"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 绝对不再乱改大类 ID，完全遵循首页源码
CLASSES = [
    {"type_id": "dianying",    "type_name": "电影"},
    {"type_id": "dianshiju",   "type_name": "电视剧"},
    {"type_id": "zongyi",      "type_name": "综艺"},
    {"type_id": "dongman",     "type_name": "动漫"},
    {"type_id": "donghuapian", "type_name": "动画片"},
    {"type_id": "duanju",      "type_name": "短剧"},
]

# 筛选结构（把子类作为剧情筛选，大类保留）
_SUB_CLASS = {
    "dianying":    [("全部", ""), ("动作", "dongzuopian"), ("喜剧", "xijupian"), ("爱情", "aiqingpian"), ("科幻", "kehuanpian"), ("恐怖", "kongbupian"), ("剧情", "juqingpian"), ("战争", "zhanzhengpian"), ("纪录", "jilupian")],
    "dianshiju":   [("全部", ""), ("国产", "guochanju"), ("香港", "xianggangju"), ("台湾", "taiwanju"), ("日本", "ribenju"), ("泰国", "taiguoju"), ("韩国", "hanguoju"), ("欧美", "oumeiju"), ("海外", "haiwaiju")],
    "zongyi":      [("全部", ""), ("大陆", "daluzongyi"), ("港台", "gangtaizongyi"), ("日韩", "rihanzongyi"), ("欧美", "oumeizongyi")],
    "dongman":     [("全部", ""), ("国产", "guochandongman"), ("日韩", "rihandongman"), ("港台", "gangtaidongman"), ("欧美", "oumeidongman"), ("海外", "haiwaidongman")],
    "donghuapian": [("全部", "")],
    "duanju":      [("全部", ""), ("女频", "nvpinlianai"), ("反转", "fanzhuanshuangju"), ("穿越", "niandaichuanyue"), ("悬疑", "naodongxuanyi"), ("都市", "xiandaidushi"), ("仙侠", "guzhuangxianxia"), ("热血", "rexuejuqing")],
}

_AREAS = [("全部", ""), ("内地", "内地"), ("大陆", "大陆"), ("香港", "香港"), ("台湾", "台湾"), ("美国", "美国"), ("日本", "日本"), ("韩国", "韩国"), ("英国", "英国"), ("法国", "法国"), ("泰国", "泰国"), ("印度", "印度"), ("意大利", "意大利"), ("西班牙", "西班牙"), ("加拿大", "加拿大"), ("德国", "德国"), ("新加坡", "新加坡"), ("其他", "其他")]
_YEARS = [("全部", "")] + [(str(y), str(y)) for y in range(2026, 1999, -1)]
_LANGS = [("全部", ""), ("国语", "国语"), ("英语", "英语"), ("粤语", "粤语"), ("闽南语", "闽南语"), ("韩语", "韩语"), ("日语", "日语"), ("其它", "其它")]
_LETTERS = [("全部", "")] + [(chr(i), chr(i)) for i in range(65, 91)] + [("0-9", "0-9")]
_SORTS = [("按时间", "time"), ("按人气", "hits"), ("按评分", "score")]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "剧情", "value": [{"n": n, "v": v} for n, v in _SUB_CLASS.get(tid, [])]},
        {"key": "area", "name": "地区", "value": [{"n": n, "v": v} for n, v in _AREAS]},
        {"key": "year", "name": "年份", "value": [{"n": n, "v": v} for n, v in _YEARS]},
        {"key": "lang", "name": "语言", "value": [{"n": n, "v": v} for n, v in _LANGS]},
        {"key": "letter", "name": "字母", "value": [{"n": n, "v": v} for n, v in _LETTERS]},
        {"key": "sort", "name": "排序", "value": [{"n": n, "v": v} for n, v in _SORTS]},
    ]

# ===================== 终极三段式解析法 =====================
# 为什么之前失败？因为源码里 <a> 标签可能会换行，属性顺序也可能变！
# 下面用独立的正则，先把链接、标题、图片分别抓出来，再进行组合。
_RE_ITEM_LINK = re.compile(r'href="(/voddetail/[^"]+\.html)"', re.I)
_RE_ITEM_TITLE = re.compile(r'title="([^"]+)"', re.I)
_RE_ITEM_PIC = re.compile(r'data-original="([^"]+)"', re.I)

# 详情页正则
_RE_H1 = re.compile(r'<h1 class="title">([\s\S]*?)</h1>', re.I)
_RE_H1_SCORE = re.compile(r'<span class="score[^"]*">([\d.]+)</span>', re.I)
_RE_PIC = re.compile(r'<div class="stui-content__thumb">[\s\S]*?<img[^>]*?data-original="([^"]+)"', re.S | re.I)
_RE_INTRO = re.compile(r'<p class="desc hidden-xs">\s*<span class="left text-muted">简介：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_INTRO_TAIL = re.compile(r'想看更多的.*?请关注我们的网站：[\s\S]*$', re.S | re.I)
_RE_DIRECTOR = re.compile(r'导演：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_ACTOR = re.compile(r'主演：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_TYPE = re.compile(r'类型：</span>([\s\S]*?)<span class="split-line">', re.S | re.I)
_RE_AREA = re.compile(r'地区：</span>([\s\S]*?)<span class="split-line">', re.S | re.I)
_RE_YEAR = re.compile(r'年份：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_EPISODE = re.compile(r'<li\s*[^>]*><a\s+href="(/vodplay/[^"]+?-(\d+)-(\d+)\.html)"[^>]*title="([^"]+)"', re.I)
_RE_TAB = re.compile(r'<a data-toggle="tab" href="#down(\d+)">([^<]+)</a>', re.I)
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)
_RE_PAGE_NUM = re.compile(r'<span class="num">\d+/(\d+)</span>')
_RE_TAIL = re.compile(r'href="[^"]*?(\d+)\.html">尾页')


class Spider(Spider):

    def getName(self):
        return "首映网"

    def init(self, extend=""):
        self.site_url = HOST
        self.headers = {"User-Agent": UA, "Referer": self.site_url + "/"}
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}

    def _fetch(self, url, timeout=20):
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=timeout)
            return rsp.text if hasattr(rsp, "text") else rsp.content.decode("utf-8", "ignore")
        except Exception as e:
            self.log(f"fetch FAIL {url} -> {e}")
            return ""

    def _clean(self, s):
        if not s: return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        return s.replace("&nbsp;", " ").replace("\xa0", " ").replace("&amp;", "&").replace("&quot;", '"').strip()

    def _valid_pic(self, url):
        if not url or url.startswith("file:///") or url == "/": return self.default_pic
        return url if url.startswith("http") else ("https:" + url if url.startswith("//") else self.site_url + url)

    def _extract_videos(self, html):
        videos, seen = [], set()
        if not html: return videos
        
        # 核心修复：不再依赖 <a> 标签的整体匹配，而是按块扫描
        # 先把网页切成以 <li 为边界的块，然后在每个块里找链接、标题、图片
        blocks = re.findall(r'<li[\s\S]*?</li>', html, re.I)
        for block in blocks:
            m_link = _RE_ITEM_LINK.search(block)
            if not m_link: continue
            
            href = m_link.group(1).replace("&amp;", "&")
            if href in seen: continue
            
            m_title = _RE_ITEM_TITLE.search(block)
            m_pic = _RE_ITEM_PIC.search(block)
            
            title = self._clean(m_title.group(1)) if m_title else "未知视频"
            pic = self._valid_pic(m_pic.group(1)) if m_pic else self.default_pic
            
            seen.add(href)
            videos.append({
                "vod_id": href, 
                "vod_name": title[:100], 
                "vod_pic": pic, 
                "vod_remarks": ""
            })
            
        return videos

    def _page_count(self, html):
        if not html: return 1
        m = _RE_PAGE_NUM.search(html) or _RE_TAIL.search(html)
        return int(m.group(1)) if m else 1

    def homeContent(self, filter=False):
        html = self._fetch(self.site_url + "/")
        return {"class": CLASSES, "filters": FILTERS, "list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try: extend = json.loads(extend)
            except: extend = {}
        if not extend: extend = {}

        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"): del extend[k]

        # 如果选了具体的剧情（子分类），cid 用剧情；否则用大类 tid
        cid = extend.get("class") or tid
        page_s = "" if page <= 1 else str(page)
        
        # 严格拼接 11 段 URL
        url = (f"{self.site_url}/vodshow/{cid}-{extend.get('area','')}-{extend.get('lang','')}-"
               f"{extend.get('letter','')}-{extend.get('sort','time')}--------{page_s}---{extend.get('year','')}.html")
        
        self.log(f"category: {url}")
        html = self._fetch(url)
        
        return {"list": self._extract_videos(html), "page": page, "pagecount": self._page_count(html), "limit": 30, "total": 999}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        url = f"{self.site_url}/vodsearch/-------------.html?wd={kw}" if page <= 1 else f"{self.site_url}/vodsearch/--------{page}---.html?wd={kw}"
        html = self._fetch(url)
        return {"list": self._extract_videos(html), "page": page, "pagecount": 1, "limit": 30, "total": 999}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids: return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self.site_url + vod_id
        html = self._fetch(url)
        if not html: return {"list": []}

        name, score = "", ""
        m = _RE_H1.search(html)
        if m:
            raw = m.group(1)
            ms = _RE_H1_SCORE.search(raw)
            if ms: score = ms.group(1)
            name = self._clean(re.sub(r'<span class="score[^"]*">[\d.]+</span>', '', raw))
        name = name or vod_id

        pic = self.default_pic
        m = _RE_PIC.search(html)
        if m: pic = self._valid_pic(m.group(1))

        content = ""
        m = _RE_INTRO.search(html)
        if m: content = _RE_INTRO_TAIL.sub("", self._clean(m.group(1))).strip()
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        def _grab(reg):
            mm = reg.search(html)
            return self._clean(re.sub(r"<[^>]+>", " ", mm.group(1))).strip(" ,，") if mm else ""
        
        director, actor = _grab(_RE_DIRECTOR), _grab(_RE_ACTOR)
        type_, area, year = _grab(_RE_TYPE), _grab(_RE_AREA), _grab(_RE_YEAR)

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
