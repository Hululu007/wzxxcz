# coding=utf-8
"""
大米星球 TVBox Python 爬虫 (基于 dmxq40.com 实际结构修正版)
"""

import sys
import re
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
                adapter = _rq.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, timeout=15, **kw):
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[dmxq]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


# 默认域名，可在 TVBox 配置中通过 {"site":"https://xxx"} 覆盖
HOST = "https://dmxq40.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

CLASSES = [
    {"type_id": "20", "type_name": "电影"},
    {"type_id": "21", "type_name": "电视剧"},
    {"type_id": "36", "type_name": "短剧"},
    {"type_id": "22", "type_name": "动漫"},
    {"type_id": "23", "type_name": "综艺"},
]

_YEARS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_SORTS = [
    {"n": "时间", "v": "time"},
    {"n": "人气", "v": "hits"},
    {"n": "评分", "v": "score"},
]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"}]},
        {"key": "class", "name": "剧情", "value": [{"n": "全部", "v": ""}, {"n": "剧情", "v": "剧情"}, {"n": "喜剧", "v": "喜剧"}, {"n": "动作", "v": "动作"}, {"n": "爱情", "v": "爱情"}, {"n": "科幻", "v": "科幻"}]},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]


class Spider(Spider):

    def getName(self):
        return "大米星球"

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
        self._play_cache = {}
        self.log("init site =", self.site_url)

    # ===================== 基础工具 =====================

    def _fetch(self, url, timeout=20, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            r = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(r, "text"):
                return r.text or ""
            if hasattr(r, "content"):
                return r.content.decode("utf-8", "ignore")
            return str(r)
        except Exception as e:
            self.log("fetch fail:", url, e)
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
        s = (s.replace("&nbsp;", " ")
              .replace("\xa0", " ")
              .replace("&amp;", "&")
              .replace("&quot;", '"')
              .replace("&#39;", "'")
              .replace("&lt;", "<")
              .replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ===================== 列表提取（兼容多种卡片结构） =====================

    def _extract_list(self, html):
        items = []
        seen = set()
        if not html:
            return items

        # 策略：先找所有详情页链接，再在其周围提取信息
        for m in re.finditer(r'href="(/voddetail/[^"]+?\.html)"', html):
            href = m.group(1)
            if href in seen:
                continue
            seen.add(href)

            # 截取链接前后的 HTML 块，用于提取标题、图片等
            start = max(0, m.start() - 600)
            end = min(len(html), m.end() + 900)
            block = html[start:end]

            # 1. 标题：分类页/首页标题在 module-poster-item-title，搜索页在 strong/em 或 title 属性
            title = ""
            title_match = re.search(r'<div class="module-poster-item-title"[^>]*>([\s\S]*?)</div>', block, re.I)
            if title_match:
                title = self._clean(title_match.group(1))
            if not title:
                title_match = re.search(r'<strong><em>(.*?)</em></strong>', block, re.S | re.I)
                if title_match:
                    title = self._clean(title_match.group(1))
            if not title:
                title_match = re.search(r'title="([^"]*)"', block, re.I)
                if title_match:
                    title = self._clean(title_match.group(1))
            if not title:
                title = href

            # 2. 封面：优先 data-original，其次 src
            pic = ""
            pic_match = re.search(r'<img[^>]*?(?:data-original|src)="([^"]+)"', block, re.I)
            if pic_match:
                pic = self._fix_url(pic_match.group(1))

            # 3. 备注：如 "HD"、"全24集"
            remark = ""
            remark_match = re.search(r'<div class="module-item-note">([^<]*)</div>', block, re.I)
            if remark_match:
                remark = self._clean(remark_match.group(1))

            items.append({
                "vod_id": href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })

        return items

    def _page_count(self, html):
        if not html:
            return 1
        m = re.search(r'title="尾页"[^>]*href="([^"]+?)"', html, re.I)
        if not m:
            m = re.search(r'href="([^"]+?)"[^>]*title="尾页"', html, re.I)
        if m:
            mm = re.search(r'(\d+)---', m.group(1))
            if mm:
                try:
                    return int(mm.group(1))
                except Exception:
                    pass
        return 9999

    # ===================== TVBox 接口实现 =====================

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/index/home.html")
        return {"list": self._extract_list(html)}

    def categoryContent(self, tid, pg, filter, extend):
        # 处理 extend 参数：可能是字符串或字典，并过滤掉空值和"全部"
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        # 清理筛选值：空字符串、"全部"都视为不筛选
        def clean_val(v):
            return "" if v in ("", "全部", None) else v

        area = clean_val(extend.get('area', ''))
        cls = clean_val(extend.get('class', ''))
        sort = clean_val(extend.get('sort', ''))
        year = clean_val(extend.get('year', ''))

        page = int(pg) if pg else 1

        # 构建 URL 的中间筛选部分
        mid_parts = []
        if area: mid_parts.append(urllib.parse.quote(area))
        if cls: mid_parts.append(urllib.parse.quote(cls))
        if sort and sort != 'time': mid_parts.append(sort)

        mid = "-".join(mid_parts)

        # 根据实际 HTML 观察到的 URL 规律拼接
        # 无筛选：/vodshow/20-----------.html 或 /vodshow/20-----------2026.html
        # 有筛选：/vodshow/20-大陆----------2026.html
        # 第2页：/vodshow/20--------2---2026.html
        if mid:
            base = f"{tid}-{mid}"
            if page == 1:
                url = f"{self.site_url}/vodshow/{base}{'-'*10}{year}.html"
            else:
                url = f"{self.site_url}/vodshow/{base}{'-'*7}{page}---{year}.html"
        else:
            if page == 1:
                url = f"{self.site_url}/vodshow/{tid}{'-'*11}{year}.html"
            else:
                url = f"{self.site_url}/vodshow/{tid}{'-'*8}{page}---{year}.html"

        self.log("category URL:", url)
        html = self._fetch(url)
        self.log("  HTML 长度:", len(html))
        videos = self._extract_list(html)
        self.log("  提取到视频数:", len(videos))
        pagecount = self._page_count(html)

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key, safe="")
        
        if page == 1:
            url = f"{self.site_url}/vodsearch/{kw}-------------.html"
        else:
            url = f"{self.site_url}/vodsearch/{kw}----------{page}---.html"

        self.log("search URL:", url)
        html = self._fetch(url)
        videos = self._extract_list(html)

        return {
            "list": videos,
            "page": page,
            "pagecount": self._page_count(html),
            "limit": 24,
            "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}

        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail:", url)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
            if m:
                name = self._clean(m.group(1).split("-")[0].split("_")[0])
        if not name:
            name = vod_id

        # 封面
        pic = ""
        m = re.search(r'<div class="module-item-pic">\s*<img[^>]*?src="([^"]+)"', html, re.S | re.I)
        if not m:
            m = re.search(r'<img[^>]*?data-original="([^"]+)"', html, re.S | re.I)
        if m:
            pic = self._fix_url(m.group(1))

        # 简介
        content = ""
        m = re.search(r'<div class="module-info-introduction-content[^"]*"[^>]*>([\s\S]*?)</div>', html, re.S | re.I)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(r'<meta name="description" content="([^"]*)"', html, re.I)
            if m:
                content = self._clean(m.group(1))

        # 导演、主演
        director = ""
        m = re.search(r'<span class="module-info-item-title">导演：</span>\s*<div class="module-info-item-content">([\s\S]*?)</div>', html, re.S | re.I)
        if m:
            director = self._clean(m.group(1))

        actor = ""
        m = re.search(r'<span class="module-info-item-title">主演：</span>\s*<div class="module-info-item-content">([\s\S]*?)</div>', html, re.S | re.I)
        if m:
            actor = self._clean(m.group(1))

        # 播放列表提取
        source_tabs = re.findall(r'<div class="module-tab-item tab-item[^"]*"[^>]*data-dropdown-value="([^"]+)"', html, re.I)
        play_groups = {}
        for m in re.finditer(r'href="(/vodplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*?><span>([^<]+)</span>', html, re.I):
            href, vid, sid, nid, ep = m.groups()
            sid = int(sid)
            play_groups.setdefault(sid, []).append((self._clean(ep), self._fix_url(href)))

        if not play_groups:
            return {"list": []}

        play_from = []
        play_url = []
        sorted_sids = sorted(play_groups.keys())
        
        for i, sid in enumerate(sorted_sids):
            alias = source_tabs[i] if i < len(source_tabs) else f"线路{sid}"
            play_from.append(alias)
            eps = play_groups[sid]
            play_url.append("#".join(f"{n}${u}" for n, u in eps))

        return {
            "list": [{
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": content,
                "vod_actor": actor,
                "vod_director": director,
                "vod_remarks": f"{len(play_groups)}条线路",
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player:", play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        url = ""

        m = re.search(r'player_aaaa\s*=\s*({.*?})\s*</script>', html, re.S)
        if not m:
            m = re.search(r'player_aaaa\s*=\s*({.*?})\s*;', html, re.S)

        if m:
            raw = m.group(1)
            try:
                data = json.loads(raw)
                url = data.get("url") or ""
            except Exception as e:
                self.log("player json fail:", e)
                mm = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if mm:
                    url = mm.group(1)

        if url:
            url = url.replace("\\/", "/").replace("&amp;", "&")
            if url.startswith("//"):
                url = "https:" + url

            res = {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
            self._play_cache[play_page] = (now, res)
            self.log("player url:", url[:200])
            return res

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
            r = self.fetch(url, headers={"User-Agent": UA, "Referer": self.site_url + "/"}, timeout=15)
            content = r.content
            ctype = r.headers.get("Content-Type", "image/jpeg")
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
