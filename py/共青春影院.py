# coding=utf-8
"""
共青春影院 gqc.ink | TVBox Python 爬虫
严格按 gqc.ink 真实页面结构解析（vfed 模板）
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
                print("[gqc]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://gqc.ink"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = "https://p0.meituan.net/csc/05e9a27d1d83478cd5475ac439d505f27627.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 首页可见频道（严格按导航栏）
CLASSES = [
    {"type_id": "dianying",  "type_name": "电影"},
    {"type_id": "lianxuju",  "type_name": "连续剧"},
    {"type_id": "zongyi",    "type_name": "综艺"},
    {"type_id": "dongman",   "type_name": "动漫"},
    {"type_id": "duanju",    "type_name": "短剧"},
]

# 分类列表页的子分类（对应 /fenlei/{xxx}.html 与 /vodshow/{xxx}...）
_SUB_CLASS = {
    "dianying": [
        ("全部", ""),
        ("动作片", "dongzuo"), ("喜剧片", "xiju"), ("爱情片", "aiqing"),
        ("科幻片", "kehuan"), ("恐怖片", "kongbu"), ("剧情片", "juqing"),
        ("战争片", "zhanzheng"), ("纪录片", "jilupian"), ("动画片", "donghuapian"),
    ],
    "lianxuju": [
        ("全部", ""),
        ("大陆剧", "mainland"), ("TVB", "tvb"), ("韩剧", "hanju"),
        ("美剧", "meiju"), ("日剧", "japan"), ("海外剧", "other"),
        ("台剧", "taiwan"),
    ],
    "zongyi": [
        ("全部", ""),
        ("大陆综艺", "mainland"), ("港台综艺", "hktw"), ("日韩综艺", "rh"),
        ("欧美综艺", "om"),
    ],
    "dongman": [
        ("全部", ""),
        ("国漫", "guoman"), ("日漫", "riman"), ("欧美动漫", "omdm"),
    ],
    "duanju": [
        ("全部", ""),
        ("短剧", "duanju"),
    ],
}

# 地区筛选（对照源码里的 /vodshow/...-%E5%86%85%E5%9C%B0...）
_AREAS = [
    ("全部", ""),
    ("内地", "内地"), ("中国香港", "中国香港"), ("中国台湾", "中国台湾"),
    ("美国", "美国"), ("韩国", "韩国"), ("日本", "日本"), ("泰国", "泰国"),
    ("英国", "英国"), ("法国", "法国"), ("德国", "德国"), ("印度", "印度"),
    ("加拿大", "加拿大"), ("俄罗斯", "俄罗斯"), ("其它", "其它"),
]

# 年份（源码里是从 2026 往回递减）
_YEARS = [("全部", "")] + [(str(y), str(y)) for y in range(2026, 1969, -1)]


def _build_filters():
    filters = {}
    for c in CLASSES:
        tid = c["type_id"]
        filters[tid] = [
            {"key": "class", "name": "分类",
             "value": [{"n": n, "v": v} for n, v in _SUB_CLASS.get(tid, [("全部", "")])]},
            {"key": "area", "name": "地区",
             "value": [{"n": n, "v": v} for n, v in _AREAS]},
            {"key": "year", "name": "年份",
             "value": [{"n": n, "v": v} for n, v in _YEARS]},
            {"key": "sort", "name": "排序",
             "value": [
                 {"n": "按时间", "v": "time"},
                 {"n": "按人气", "v": "hits"},
                 {"n": "按评分", "v": "score"},
             ]},
        ]
    return filters


FILTERS = _build_filters()


# ===================== 正则 =====================
# 首页 / 列表页 卡片：<a class="fed-list-pics ... href="/neirong/356750.html" data-original="...">
_RE_CARD = re.compile(
    r'<a[^>]*class="fed-list-pics[^"]*"[^>]*href="(/neirong/\d+\.html)"[^>]*'
    r'data-original="([^"]+)"[^>]*>([\s\S]*?)</a>\s*'
    r'<a[^>]*class="fed-list-title[^"]*"[^>]*href="/neirong/\d+\.html"[^>]*>([^<]+)</a>',
    re.S | re.I)

_RE_LIST_TITLE = re.compile(
    r'<a[^>]*class="fed-list-title[^"]*"[^>]*href="(/neirong/\d+\.html)"[^>]*>([^<]+)</a>',
    re.I)

_RE_REMARKS = re.compile(
    r'<span[^>]*class="fed-list-remarks[^"]*"[^>]*>([^<]+)</span>',
    re.I)

_RE_SCORE_SPAN = re.compile(
    r'<span[^>]*class="fed-list-score[^"]*"[^>]*>([\d.]+)</span>',
    re.I)

_RE_DESC = re.compile(
    r'<span[^>]*class="fed-list-desc[^"]*"[^>]*>([\s\S]*?)</span>',
    re.S | re.I)

# 详情页
_RE_H1 = re.compile(r'<h1[^>]*class="fed-part-eone[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>',
                    re.I)
_RE_DETAIL_PIC = re.compile(
    r'<a[^>]*class="fed-list-pics[^"]*"[^>]*data-original="([^"]+)"', re.I)
_RE_ACTOR_BLOCK = re.compile(
    r'<span class="fed-text-muted">主演：</span>([\s\S]*?)</li>', re.I)
_RE_DIRECTOR_BLOCK = re.compile(
    r'<span class="fed-text-muted">导演：</span>([\s\S]*?)</li>', re.I)
_RE_LINK_TEXT = re.compile(r'<a[^>]*>([^<]*)</a>', re.I)
_RE_CAT = re.compile(
    r'<span class="fed-text-muted">分类：</span>\s*<a[^>]*>([^<]+)</a>', re.I)
_RE_AREA = re.compile(
    r'<span class="fed-text-muted">地区：</span>\s*<a[^>]*>([^<]+)</a>', re.I)
_RE_YEAR = re.compile(
    r'<span class="fed-text-muted">年份：</span>\s*<a[^>]*>([^<]+)</a>', re.I)
_RE_UPD = re.compile(
    r'<span class="fed-text-muted">更新：</span>([^<]+)</li>', re.I)
_RE_INTRO_DIV = re.compile(
    r'<div class="fed-part-esan">\s*<span class="fed-text-muted">简介：</span>'
    r'[\s\S]*?</a>([\s\S]*?)</div>', re.S | re.I)
_RE_INTRO_P = re.compile(
    r'<p class="fed-padding fed-part-both fed-text-muted">([\s\S]*?)</p>',
    re.S | re.I)
_RE_DETAIL_REMARKS = re.compile(
    r'<span class="fed-list-remarks[^"]*"[^>]*>([^<]+)</span>', re.I)
_RE_DETAIL_SCORE = re.compile(
    r'<span class="fed-list-score[^"]*"[^>]*>([\d.]+)</span>', re.I)

# 剧集：线路按钮
_RE_LINE_A = re.compile(
    r'<li[^>]*class="[^"]*fed-drop-btns[^"]*"[^>]*>\s*'
    r'<a[^>]*href="([^"]+)"[^>]*>\s*([^<\s][^<]*?)\s*'
    r'<span[^>]*class="[^"]*"[^>]*>\s*(\d+)\s*</span>',
    re.S | re.I)

# 每条线路的集数块：<div class="fed-play-item ..."> ... </div>
_RE_PLAY_ITEM = re.compile(
    r'<div class="fed-play-item[^"]*">([\s\S]*?)</ul>\s*</div>',
    re.S | re.I)
_RE_EP_A = re.compile(
    r'<a[^>]*class="fed-btns-info[^"]*"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>',
    re.I)
_RE_EP_HREF_NID = re.compile(r'-(\d+)\.html$', re.I)
_RE_EP_HREF_SID = re.compile(r'/bofang/(\d+)-(\d+)-(\d+)\.html', re.I)

# 播放页：iframe 的 data-play / data-next
_RE_IFRAME_DATA_PLAY = re.compile(
    r'<iframe[^>]*id="fed-play-iframe"[^>]*data-play="([^"]*)"', re.S | re.I)
_RE_IFRAME_DATA_PARS = re.compile(
    r'<iframe[^>]*id="fed-play-iframe"[^>]*data-pars="([^"]*)"', re.S | re.I)
_RE_IFRAME_DATA_NEXT = re.compile(
    r'<iframe[^>]*id="fed-play-iframe"[^>]*data-next="([^"]*)"', re.S | re.I)

# 分页
_RE_PAGE_DATA_URL = re.compile(
    r'class="fed-btns-info[^"]*fed-page-jump"[^>]*data-url="([^"]+)"', re.I)


class Spider(Spider):

    def getName(self):
        return "共青春影院"

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
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础工具 ----------------
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

    # ---------------- 首页 & 分类 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        videos = self._extract_list(html)
        return {"list": videos}

    def _extract_list(self, html):
        """首页/列表页：按卡片结构抓取"""
        videos = []
        seen = set()
        if not html:
            return videos

        # 每张卡片 = 图片 a + 标题 a + 备注 span + 描述 span
        # 用 fed-list-item li 作为分割块来提取更稳
        for block in re.findall(
                r'<li class="fed-list-item[\s\S]*?</li>', html, re.I):
            m_img = re.search(
                r'<a[^>]*class="fed-list-pics[^"]*"[^>]*href="(/neirong/\d+\.html)"'
                r'[^>]*data-original="([^"]+)"', block, re.I)
            m_title = re.search(
                r'<a[^>]*class="fed-list-title[^"]*"[^>]*href="/neirong/\d+\.html"'
                r'[^>]*>([^<]+)</a>', block, re.I)
            if not m_img or not m_title:
                continue
            href = m_img.group(1)
            if href in seen:
                continue
            seen.add(href)
            pic = m_img.group(2)
            name = self._clean(m_title.group(1))
            m_rm = re.search(
                r'<span[^>]*class="fed-list-remarks[^"]*"[^>]*>([^<]+)</span>',
                block, re.I)
            remarks = self._clean(m_rm.group(1)) if m_rm else ""
            m_desc = re.search(
                r'<span[^>]*class="fed-list-desc[^"]*"[^>]*>([\s\S]*?)</span>',
                block, re.S | re.I)
            desc = self._clean(m_desc.group(1)) if m_desc else ""

            videos.append({
                "vod_id": href,
                "vod_name": name[:100],
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks or desc[:30],
            })
        return videos

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        # 取筛选
        sub = extend.get("class") or ""
        area = extend.get("area") or ""
        year = extend.get("year") or ""
        sort = extend.get("sort") or "time"

        # /vodshow/{sub}--{sort}---{area}--{year}--{page}.html
        # gqc 的 vodshow 参数顺序: 分类-排序-地区-年份-页码
        # 参照源码: /vodshow/mainland-----------2026.html   (page 在 year 前一段)
        # 分页:    /vodshow/mainland--------2---2026.html
        base_sub = sub if sub else tid

        # 地区 URL 编码
        area_enc = urllib.parse.quote(area) if area else ""

        # 分类路径：分类 - 排序 - 地区 - 年份 - 页码
        # /vodshow/{cat}--{sort}--{area}--{year}--{page}.html
        # 源码分页示例: /vodshow/mainland--------2---2026.html
        # 即：cat = mainland, sort = "", area = "", page = 2, year = 2026
        if page > 1:
            path = "/vodshow/%s--%s--%s--%s---%s.html" % (
                base_sub, "", area_enc, year, page)
            # 上面的 ---%s 会多一个 -，调整为 gqc 实际格式
            # 实际: mainland--------2---2026.html
            # 拆: mainland -- (空) -- (空) -- 2 -- (空) -- 2026
            # 直接按位置拼：
            path = "/vodshow/%s----%s---%s.html" % (base_sub, page, year)
        else:
            path = "/vodshow/%s---------%s.html" % (base_sub, year)

        # 排序切换（源码：按时间 / 按人气 / 按评分）
        if sort in ("hits", "score"):
            if page > 1:
                path = "/vodshow/%s--%s------%s---%s.html" % (
                    base_sub, sort, page, year)
            else:
                path = "/vodshow/%s--%s--------%s.html" % (
                    base_sub, sort, year)

        url = self.site_url + path
        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._extract_list(html)
        pagecount = self._page_count(html)

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def _page_count(self, html):
        if not html:
            return 1
        # 源码: data-total="15"
        m = re.search(r'data-total="(\d+)"', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        pages = re.findall(r'page=(\d+)', html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        return 1

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        """gqc.ink 搜索接口有验证码拦截，返回空列表。"""
        return {"list": [], "page": 1, "pagecount": 0, "limit": 0, "total": 0}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 ----------------
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
            m = re.search(r'<title>(.*?)</title>', html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_DETAIL_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        # 主演 / 导演
        actor = ""
        m = _RE_ACTOR_BLOCK.search(html)
        if m:
            names = _RE_LINK_TEXT.findall(m.group(1))
            actor = ", ".join(self._clean(n) for n in names if self._clean(n))

        director = ""
        m = _RE_DIRECTOR_BLOCK.search(html)
        if m:
            names = _RE_LINK_TEXT.findall(m.group(1))
            director = ", ".join(self._clean(n) for n in names if self._clean(n))

        # 分类 / 地区 / 年份 / 更新
        cat = ""
        m = _RE_CAT.search(html)
        if m:
            cat = self._clean(m.group(1))

        area = ""
        m = _RE_AREA.search(html)
        if m:
            area = self._clean(m.group(1))

        year = ""
        m = _RE_YEAR.search(html)
        if m:
            year = self._clean(m.group(1))

        remarks = ""
        m = _RE_DETAIL_REMARKS.search(html)
        if m:
            remarks = self._clean(m.group(1))

        score = ""
        m = _RE_DETAIL_SCORE.search(html)
        if m:
            score = m.group(1)

        # 简介
        content = ""
        m = _RE_INTRO_DIV.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_INTRO_P.search(html)
            if m:
                content = self._clean(m.group(1))
        if not content:
            m = re.search(
                r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html, re.I)
            if m:
                content = self._clean(m.group(1))
        content = INTRO_PREFIX + "\n" + content if content else INTRO_PREFIX

        # ------- 剧集 -------
        # 1) 先抓每条线路名和 sid（/bofang/{id}-{sid}-1.html）
        line_map = {}   # sid -> 线路名
        line_order = []
        for m in _RE_LINE_A.finditer(html):
            href, lname, _cnt = m.group(1), m.group(2), m.group(3)
            mm = _RE_EP_HREF_SID.search(href)
            if not mm:
                continue
            sid = mm.group(2)
            lname = self._clean(lname)
            if sid not in line_map:
                line_map[sid] = lname or ("线路%s" % sid)
                line_order.append(sid)

        # 2) 抓所有 fed-play-item 块，按出现顺序对应线路
        groups = {}
        items = _RE_PLAY_ITEM.findall(html)
        self.log("play items: %d, lines: %d" % (len(items), len(line_order)))

        for idx, block in enumerate(items):
            if idx >= len(line_order):
                break
            sid = line_order[idx]
            eps = []
            for em in _RE_EP_A.finditer(block):
                e_href = em.group(1)
                e_name = self._clean(em.group(2))
                if not e_href or "/bofang/" not in e_href:
                    continue
                if e_href.startswith("/"):
                    e_href = self.site_url + e_href
                e_href = e_href.replace("&amp;", "&")
                if not e_name:
                    mn = _RE_EP_HREF_NID.search(e_href)
                    e_name = "第%s集" % (mn.group(1) if mn else "1")
                eps.append((e_name, e_href))
            if eps:
                groups[sid] = eps

        self.log("detail episodes: %s" % {k: len(v) for k, v in groups.items()})

        if not groups:
            return {"list": []}

        play_from = []
        play_url = []
        for sid in line_order:
            if sid not in groups:
                continue
            alias = line_map.get(sid, "线路%s" % sid)
            play_from.append(alias)
            play_url.append(
                "#".join("%s$%s" % (n, h) for n, h in groups[sid]))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remarks or ("%d条线路" % len(groups)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        real = ""

        if html:
            m = _RE_IFRAME_DATA_PLAY.search(html)
            if m:
                real = (m.group(1) or "").strip()

            # data-play 为空时，拼 data-pars（解析接口）
            if not real:
                mp = _RE_IFRAME_DATA_PARS.search(html)
                if mp:
                    pars = (mp.group(1) or "").strip()
                    if pars:
                        # 这种情况交给 TVBox 嗅探，直接用播放页
                        res = {
                            "parse": 1,
                            "playUrl": "",
                            "url": play_page,
                            "header": {
                                "User-Agent": UA,
                                "Referer": self.site_url + "/",
                            },
                        }
                        self._play_cache[play_page] = (now, res)
                        return res

            if real.startswith("//"):
                real = "https:" + real
            real = real.replace("&amp;", "&")

        if real and ".m3u8" in real.lower():
            res = {
                "parse": 0,
                "playUrl": "",
                "url": real,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
            self._play_cache[play_page] = (now, res)
            self.log("=> m3u8: %s" % real[:160])
            return res

        # 兜底：交给 TVBox 嗅探
        res = {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": {
                "User-Agent": UA,
                "Referer": self.site_url + "/",
            },
        }
        self._play_cache[play_page] = (now, res)
        return res

    # ---------------- 其他 ----------------
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
