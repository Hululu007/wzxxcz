# coding=utf-8
"""
枫叶影院 926dy.com | TVBox Python 爬虫
网站: https://www.926dy.com/
模板: 聚丰 (jufeng) MacCMS
关键:
  - 详情页视频列表: resource-box-nav 线路名 + rb-item 剧集列表
  - 播放页 player_aaaa 对象，url 为 URL 编码的真实 m3u8 地址
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
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[fengye]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.926dy.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/jufeng/img/logo_black.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ============== 分类 ==============
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "连续剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "34", "type_name": "短剧"},
]

# 电影分类 type id (从网站实际 type/ 路径提取)
_MOVIE_CLASSES = [
    ("6", "动作片"), ("7", "喜剧片"), ("8", "爱情片"), ("9", "科幻片"),
    ("10", "恐怖片"), ("11", "剧情片"), ("12", "战争片"), ("13", "悬疑片"),
    ("14", "冒险片"), ("15", "奇幻片"), ("16", "惊悚片"), ("17", "动画片"),
    ("18", "纪录片"),
]
# 连续剧分类
_TV_CLASSES = [
    ("19", "国产剧"), ("20", "香港剧"), ("21", "韩国剧"), ("22", "美国剧"),
    ("23", "日本剧"), ("24", "台湾剧"), ("25", "泰国剧"), ("26", "英国剧"),
    ("27", "印度剧"), ("28", "法国剧"),
]
# 综艺分类
_VARIETY_CLASSES = [
    ("29", "国产综艺"), ("30", "港台综艺"), ("31", "日韩综艺"), ("32", "欧美综艺"),
]
# 动漫分类
_ANIME_CLASSES = [
    ("33", "动漫"),
]
# 短剧分类
_SHORT_CLASSES = [
    ("35", "短剧"),
]

_FILTERS_MAP = {
    "1":  _MOVIE_CLASSES,
    "2":  _TV_CLASSES,
    "3":  _VARIETY_CLASSES,
    "4":  _ANIME_CLASSES,
    "34": _SHORT_CLASSES,
}

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "中国大陆", "v": "中国大陆"}, {"n": "中国香港", "v": "中国香港"},
    {"n": "中国台湾", "v": "中国台湾"}, {"n": "美国", "v": "美国"},
    {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
    {"n": "英国", "v": "英国"}, {"n": "法国", "v": "法国"},
    {"n": "德国", "v": "德国"}, {"n": "印度", "v": "印度"},
    {"n": "泰国", "v": "泰国"}, {"n": "加拿大", "v": "加拿大"},
    {"n": "意大利", "v": "意大利"}, {"n": "西班牙", "v": "西班牙"},
]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    sub_classes = _FILTERS_MAP.get(tid, [])
    class_list = [{"n": "全部", "v": ""}] + \
                 [{"n": name, "v": cid} for cid, name in sub_classes]
    FILTERS[tid] = [
        {"key": "class", "name": "分类", "value": class_list},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
    ]


# ============== 正则 ==============

_RE_LI_ITEM = re.compile(
    r'<li\s+class="item">(.*?)(?=<li\s+class="item">|</ul>)',
    re.S | re.I)

_RE_CARD_HREF = re.compile(
    r'<a\s+href="(/post/\d+\.html)"\s+class="thumb"', re.I)
_RE_CARD_IMG = re.compile(
    r'<img[^>]*?alt="([^"]*)"[^>]*?(?:data-original|src)="([^"]*)"', re.I)
_RE_CARD_NAME = re.compile(
    r'<h5\s+class="subject">[\s\S]*?<a[^>]*>([^<]*)</a>', re.S | re.I)
_RE_CARD_TAGS = re.compile(
    r'<p\s+class="tags">([^<]*)</p>', re.I)
_RE_CARD_STATE = re.compile(
    r'<span\s+class="state">([^<]*)</span>', re.I)

_RE_H1 = re.compile(
    r'<h1\s+class="article-subject-m">([^<]+)</h1>', re.I)

_RE_THUMB = re.compile(
    r'<img[^>]*?id="movie_thumb"[^>]*?(?:data-original|src)="([^"]*)"',
    re.I)

_RE_INTRO = re.compile(
    r'<h2>详情介绍</h2>[\s\S]*?'
    r'<div\s+class="box">[\s\S]*?'
    r'<div[^>]*>([\s\S]*?)</div>[\s\S]*?'
    r'</div>',
    re.S | re.I)

_RE_TAB_NAV = re.compile(
    r'<a\s+href="javascript:;"\s+class="tab-nav">([^<]+)</a>',
    re.I)

_RE_EPISODE = re.compile(
    r'<li><a\s+href="(/watch/\d+-\d+-\d+\.html)"[^>]*>([^<]+)</a></li>',
    re.I)

_RE_EPISODES_LIST = re.compile(
    r'<ul\s+class="episodes-list[^"]*">([\s\S]*?)</ul>',
    re.S | re.I)

_RE_PLAYER_AAAA = re.compile(
    r'player_aaaa\s*=\s*(\{[\s\S]*?\});',
    re.S)

_RE_PLAYER_URL = re.compile(r'"url"\s*:\s*"([^"]*)"', re.I)
_RE_PLAYER_FROM = re.compile(r'"from"\s*:\s*"([^"]*)"', re.I)

_RE_LAST_PAGE = re.compile(
    r'title="末页"[^>]*href="[^"]*page/(\d+)\.html"', re.I)

_RE_PAGE_TOTAL = re.compile(
    r'\.\.(\d+)页', re.I)

_RE_SEARCH_TOTAL = re.compile(r'mac_record_total.*?text\((\d+)\)', re.I)


class Spider(Spider):

    def getName(self):
        return "枫叶影院"

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
            elif hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _post(self, url, data, timeout=20, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            h["Content-Type"] = "application/x-www-form-urlencoded"

            import requests as _req
            sess = getattr(self, '_sess', None)
            if sess is None:
                sess = getattr(self, '_session', None)
            if sess is None:
                rsp = _req.post(url, data=data, headers=h,
                                timeout=timeout, verify=False)
            else:
                rsp = sess.post(url, data=data, headers=h, timeout=timeout)

            if hasattr(rsp, "text"):
                return rsp.text or ""
            elif hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)
        except Exception as e:
            self.log("post FAIL %s -> %s" % (url, e))
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
        videos = []
        seen = set()
        if not html:
            return videos

        for li_m in _RE_LI_ITEM.finditer(html):
            block = li_m.group(1)
            href_m = _RE_CARD_HREF.search(block)
            if not href_m:
                continue
            href = href_m.group(1)
            if href in seen:
                continue
            seen.add(href)

            alt = ""
            pic = ""
            img_m = _RE_CARD_IMG.search(block)
            if img_m:
                alt = img_m.group(1)
                pic = img_m.group(2)

            name = ""
            name_m = _RE_CARD_NAME.search(block)
            if name_m:
                name = self._clean(name_m.group(1))

            tags = ""
            tags_m = _RE_CARD_TAGS.search(block)
            if tags_m:
                tags = self._clean(tags_m.group(1))

            state = ""
            state_m = _RE_CARD_STATE.search(block)
            if state_m:
                state = state_m.group(1).strip()

            remark = state
            if tags:
                remark = remark + " " + tags if remark else tags

            videos.append({
                "vod_id":      href,
                "vod_name":    name or alt or href,
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": remark,
            })
        return videos

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {"list": videos}

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

        use_tid = extend.get("class") or tid

        if page <= 1:
            base_url = "%s/type/%s.html" % (self.site_url, use_tid)
        else:
            base_url = "%s/type/%s/page/%d.html" % (self.site_url, use_tid, page)

        params = {}
        if extend.get("area"):
            params["area"] = extend["area"]
        if extend.get("year"):
            params["year"] = extend["year"]

        if params:
            url = base_url + "?" + urllib.parse.urlencode(params)
        else:
            url = base_url

        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)

        pagecount = 1
        m = _RE_LAST_PAGE.search(html)
        if m:
            try:
                pagecount = int(m.group(1))
            except Exception:
                pagecount = 999
        else:
            m2 = _RE_PAGE_TOTAL.search(html)
            if m2:
                try:
                    pagecount = int(m2.group(1))
                except Exception:
                    pagecount = 999
            else:
                pages = re.findall(r'/type/\d+/page/(\d+)\.html', html)
                if pages:
                    try:
                        pagecount = max(int(p) for p in pages)
                    except Exception:
                        pagecount = 999
                else:
                    pagecount = 1

        self.log("  视频: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 30, "total": pagecount * 30,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)

        if page <= 1:
            url = "%s/search/-------------.html" % self.site_url
            html = self._post(url, data="wd=%s" % keyword)
        else:
            url = "%s/search/%s----------%d---.html" % (
                self.site_url, keyword, page)
            html = self._fetch(url)

        self.log("search: %s" % url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)

        total = 0
        m = _RE_SEARCH_TOTAL.search(html)
        if m:
            try:
                total = int(m.group(1))
            except Exception:
                total = len(videos)
        else:
            total = len(videos)

        pagecount = max(1, (total + 29) // 30) if total > 0 else 1
        m_pt = re.search(r'mac_page_total.*?text\((\d+)\)', html)
        if m_pt:
            try:
                pagecount = int(m_pt.group(1))
            except Exception:
                pass

        return {
            "list": videos, "page": page,
            "pagecount": pagecount,
            "limit": 30, "total": total,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
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
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
                if name.startswith("《"):
                    name = name[1:]
                if name.endswith("》"):
                    name = name[:-1]
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        m = _RE_THUMB.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        # 修复：精准提取 导演/演员/年份/地区/豆瓣
        director = ""
        actor = ""
        year = ""
        area = ""
        score = ""
        
        # 提取所有 info-wrap 里的 p 标签内容
        info_blocks = re.findall(r'<div class="info-wrap low">([\s\S]*?)</div>', html)
        if info_blocks:
            info_html = info_blocks[0]
            # 提取所有的 label 和 span 内容
            infos = re.findall(r'<label>([^<]+)</label><span>([\s\S]*?)</span>', info_html)
            for label, value in infos:
                label = label.replace("：", "").strip()
                value = self._clean(value)
                if label == "导演":
                    director = value
                elif label == "主演":
                    actor = value
                elif label == "年份":
                    year = value
                elif label == "地区":
                    area = value
                elif label == "豆瓣":
                    score = value

        # 简介
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(
                r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
                html, re.I)
            if m:
                content = self._clean(m.group(1))
                idx = content.find("简介：")
                if idx >= 0:
                    content = content[idx + 3:]

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # 剧集提取
        tab_names = [m.group(1).strip()
                     for m in _RE_TAB_NAV.finditer(html)]
        ep_lists = _RE_EPISODES_LIST.findall(html)

        self.log("  线路名: %s, episodes-list: %d" % (tab_names, len(ep_lists)))

        groups = {}
        for i, ep_html in enumerate(ep_lists):
            if i >= len(tab_names):
                origin_name = "线路%d" % (i + 1)
            else:
                origin_name = tab_names[i]

            eps = []
            for em in _RE_EPISODE.finditer(ep_html):
                ep_href = em.group(1).replace("&amp;", "&")
                ep_name = self._clean(em.group(2))
                eps.append((ep_name, ep_href))

            if eps:
                groups[origin_name] = eps

        self.log("  剧集组: %s" % {k: len(v) for k, v in groups.items()})

        if not groups:
            return {"list": []}

        play_from = list(groups.keys())
        play_url = []
        for origin in play_from:
            eps = groups[origin]
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        remark_parts = []
        if year:
            remark_parts.append(year)
        if area:
            remark_parts.append(area)
        remark_parts.append("%d条线路" % len(groups))
        remarks = " ".join(remark_parts)

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        import time
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        if not html:
            res = {"parse": 1, "playUrl": "", "url": play_page,
                   "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
            self._play_cache[play_page] = (now, res)
            return res

        real_url = ""
        idx = html.find("player_aaaa")
        if idx >= 0:
            start = html.find("{", idx)
            if start >= 0:
                depth = 0
                in_str = False
                escape = False
                pos = start
                while pos < len(html):
                    ch = html[pos]
                    if in_str:
                        if escape:
                            escape = False
                        elif ch == '\\':
                            escape = True
                        elif ch == '"':
                            in_str = False
                    else:
                        if ch == '"':
                            in_str = True
                        elif ch == '{':
                            depth += 1
                        elif ch == '}':
                            depth -= 1
                            if depth == 0:
                                raw = html[start:pos + 1]
                                try:
                                    import json as _json
                                    obj = _json.loads(raw)
                                    url_enc = obj.get("url", "")
                                    if url_enc:
                                        real_url = urllib.parse.unquote(url_enc)
                                except Exception as e:
                                    self.log("  player_aaaa 解析失败: %s" % e)
                                break
                    pos += 1

        self.log("  解析结果: %s" % (real_url[:120] if real_url else "EMPTY"))

        if real_url and real_url.startswith("http"):
            res = {
                "parse": 0,
                "playUrl": "",
                "url": real_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
            self._play_cache[play_page] = (now, res)
            return res

        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res
