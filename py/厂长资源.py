# coding=utf-8
"""
厂长资源 czzytv77.com | TVBox Python 爬虫
- 苹果 CMS V10 + mb13 模板
- 播放页 player_aaaa 直出 m3u8 直链 (encrypt=0)
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
                print("[czzytv]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://czzytv77.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/static/images/logo.jpg"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "40", "type_name": "豆瓣Top250"},
]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2023, 2013, -1)]
_AREAS = [{"n": "全部", "v": ""},
          {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
          {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"},
          {"n": "法国", "v": "法国"}, {"n": "英国", "v": "英国"},
          {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
          {"n": "德国", "v": "德国"}, {"n": "泰国", "v": "泰国"},
          {"n": "印度", "v": "印度"}, {"n": "意大利", "v": "意大利"},
          {"n": "西班牙", "v": "西班牙"}, {"n": "加拿大", "v": "加拿大"},
          {"n": "其他", "v": "其他"}]
_ORDERS = [{"n": "按时间", "v": "time"},
           {"n": "按人气", "v": "hits"},
           {"n": "按评分", "v": "score"}]
_LANGS = [{"n": "全部", "v": ""}, {"n": "国语", "v": "国语"},
          {"n": "英语", "v": "英语"}, {"n": "粤语", "v": "粤语"},
          {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"},
          {"n": "日语", "v": "日语"}, {"n": "法语", "v": "法语"},
          {"n": "德语", "v": "德语"}, {"n": "其它", "v": "其它"}]

_FILTERS_MAP = {
    "1": ["动作电影", "喜剧电影", "爱情片", "科幻电影", "恐怖电影",
          "剧情片", "战争片", "记录片", "犯罪片", "动漫片"],
    "2": ["电视剧", "港台剧", "日韩剧", "欧美剧", "泰剧", "海外剧"],
    "3": ["内地综艺", "港台综艺", "日韩综艺", "欧美综艺"],
    "4": ["国漫", "日韩樱花动漫", "欧美动漫", "海外动漫"],
    "40": [],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    fs = [{"key": "class", "name": "分类",
           "value": [{"n": "全部", "v": ""}] +
                    [{"n": x, "v": x} for x in _FILTERS_MAP.get(tid, [])]},
          {"key": "area", "name": "地区", "value": _AREAS},
          {"key": "year", "name": "年份", "value": _YEARS},
          {"key": "order", "name": "排序", "value": _ORDERS}]
    if tid == "1":
        fs.insert(1, {"key": "lang", "name": "语言", "value": _LANGS})
    FILTERS[tid] = fs


# ============ 正则 ============
_RE_CARD = re.compile(
    r'<a[^>]*class="stui-vodlist__thumb lazyload"[^>]*'
    r'href="(/cdvoddetail/(\d+)\.html)"[\s\S]*?'
    r'title="([^"]*)"[\s\S]*?'
    r'(?:data-original|src)="([^"]*)"[\s\S]*?>'
    r'[\s\S]{0,200}?'
    r'<span class="pic-text[^"]*">([^<]*)</span>',
    re.S | re.I)

_RE_SEARCH_CARD = re.compile(
    r'<a[^>]*class="v-thumb stui-vodlist__thumb lazyload"[^>]*'
    r'href="(/cdvoddetail/(\d+)\.html)"[\s\S]*?'
    r'title="([^"]*)"[\s\S]*?'
    r'(?:data-original|src)="([^"]*)"[\s\S]*?>'
    r'[\s\S]{0,200}?'
    r'<span class="pic-text[^"]*">([^<]*)</span>',
    re.S | re.I)

_RE_PAGECOUNT = re.compile(r'<span class="num">(\d+)/(\d+)</span>')
_RE_PLAYER_AA = re.compile(r"var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>", re.I)


class Spider(Spider):

    def getName(self):
        return "厂长资源"

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
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------- 基础工具 ----------
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

    # ---------- 列表解析 ----------
    def _extract_videos(self, html, search=False):
        videos, seen = [], set()
        if not html:
            return videos
        reg = _RE_SEARCH_CARD if search else _RE_CARD
        for m in reg.finditer(html):
            href, vid, name, pic, remark = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(name) or ("影片" + vid),
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": self._clean(remark),
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = _RE_PAGECOUNT.search(html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        return 1

    # ---------- 分类 URL ----------
    def _build_show_url(self, tid, page, extend):
        q = lambda s: urllib.parse.quote(s) if s else ""
        area   = q(extend.get("area", ""))
        order  = extend.get("order", "")
        cls    = q(extend.get("class", ""))
        lang   = q(extend.get("lang", ""))
        letter = ""
        year   = extend.get("year", "")
        pg     = "" if page <= 1 else str(page)
        # type-area-order-class-lang-letter-state-page---year
        path = "%s-%s-%s-%s-%s-%s--%s---%s" % (
            tid, area, order, cls, lang, letter, pg, year)
        return "%s/cdvodshow/%s.html" % (self.site_url, path)

    # ---------- TVBox 接口 ----------
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
        extend = extend or {}
        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]
        
        if not extend and page == 1:
            url = "%s/cdvodshow/%s-----------.html" % (self.site_url, tid)
        else:
            url = self._build_show_url(tid, page, extend)
            
        self.log("category(show): %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        
        if not videos:
            url_fallback = "%s/cdvodtype/%s.html" % (self.site_url, tid)
            if page > 1:
                url_fallback = "%s/cdvodtype/%s-%d.html" % (self.site_url, tid, page)
            self.log("category(fallback): %s" % url_fallback)
            html2 = self._fetch(url_fallback)
            videos = self._extract_videos(html2)
            if videos:
                html = html2
                
        if not videos:
            snippet = html[:500].replace("\n", " ") if html else "HTML为空"
            self.log("⚠️ 解析失败，网页内容: %s" % snippet)

        return {"list": videos, "page": page, "pagecount": self._page_count(html),
                "limit": 24, "total": 9999}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        url = "%s/cdvodsearch/%s-------------%s.html" % (self.site_url, kw, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html, search=True)
        if not videos:
            url2 = "%s/cdvodsearch/-------------.html?wd=%s" % (self.site_url, kw)
            html2 = self._fetch(url2)
            videos = self._extract_videos(html2, search=True)
            html = html2 or html
        return {"list": videos, "page": page,
                "pagecount": self._page_count(html),
                "limit": 24, "total": 999}

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
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = re.search(r'<h1[^>]*class="title"[^>]*>([\s\S]*?)</h1>', html, re.I)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("-")[0].split("_")[0])

        # 封面 + 备注
        pic = self.default_pic
        remark = ""
        m = re.search(r'<a[^>]*class="stui-vodlist__thumb picture v-thumb"[\s\S]{0,400}?'
                      r'data-original="([^"]+)"', html, re.I)
        if m:
            pic = self._fix_url(m.group(1))
        m = re.search(r'<a[^>]*class="stui-vodlist__thumb picture v-thumb"[\s\S]{0,400}?'
                      r'<span class="pic-text[^"]*">([^<]*)</span>', html, re.I)
        if m:
            remark = self._clean(m.group(1))

        # 🚀 提取缺失的元信息（类型、地区、年份、语言、更新）
        meta_parts = []
        # 提取类型
        m = re.search(r'<span class="text-muted">类型：</span>([\s\S]*?)<span class="split-line">', html, re.I)
        if m:
            types = re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1))
            if types: meta_parts.append("类型：" + ",".join(types))
        # 提取地区
        m = re.search(r'<span class="text-muted">地区：</span>([\s\S]*?)<span class="split-line">', html, re.I)
        if m:
            areas = re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1))
            if areas: meta_parts.append("地区：" + ",".join(areas))
        # 提取年份
        m = re.search(r'<span class="text-muted">年份：</span>([\s\S]*?)<span class="split-line">', html, re.I)
        if m:
            years = re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1))
            if years: meta_parts.append("年份：" + ",".join(years))
        # 提取语言
        m = re.search(r'<span class="text-muted">语言：</span>([\s\S]*?)</p>', html, re.I)
        if m:
            langs = re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1))
            if langs: meta_parts.append("语言：" + ",".join(langs))
        # 提取更新
        m = re.search(r'<span class="text-muted">更新：</span>([^<]+)</p>', html, re.I)
        if m:
            meta_parts.append("更新：" + self._clean(m.group(1)))

        # 主演 / 导演
        actor = ""
        m = re.search(r'<span class="text-muted">主演：</span>([\s\S]*?)</p>', html, re.I)
        if m:
            actor = ", ".join(self._clean(x) for x in re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1)))
        director = ""
        m = re.search(r'<span class="text-muted">导演：</span>([\s\S]*?)</p>', html, re.I)
        if m:
            director = ", ".join(self._clean(x) for x in re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1)))

        # 评分
        score = ""
        m = re.search(r'<span class="branch">([\d.]+)</span>', html, re.I)
        if m:
            score = m.group(1)

        # 简介：优先 detail-content
        content = ""
        m = re.search(r'<span class="detail-content"[^>]*>([\s\S]*?)</span>', html, re.I)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(r'<span class="detail-sketch"[^>]*>([\s\S]*?)</span>', html, re.I)
            if m:
                content = self._clean(m.group(1))
        if not content:
            m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html, re.I)
            if m:
                content = self._clean(m.group(1))
                
        # 将提取到的元信息拼接到简介前面
        meta_str = " | ".join(meta_parts) + "\n" if meta_parts else ""
        content = INTRO_PREFIX + "\n" + meta_str + content

        # 剧集：按线路块
        play_from, play_url = [], []
        block_re = re.compile(
            r'<div class="stui-pannel-box b playlist mb">([\s\S]*?)</ul>\s*</div>\s*</div>\s*</div>',
            re.I)
        for block in block_re.findall(html):
            mt = re.search(r'<h3 class="title">\s*([\s\S]*?)\s*</h3>', block, re.I)
            line_name = self._clean(mt.group(1)) if mt else "线路"
            eps = re.findall(
                r'<li class="my-find-frist-play">\s*<a href="(/cdvodplay/[^"]+)">([^<]+)</a>',
                block, re.I)
            if not eps:
                continue
            play_from.append(line_name)
            play_url.append("#".join(
                "%s$%s%s" % (self._clean(ep_name), self.site_url, ep_href)
                for ep_href, ep_name in eps))

        if not play_from:
            self.log("  未解析到剧集")
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remark or ("%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("========== 准备播放 ==========")
        self.log("解析播放页: %s" % play_page)

        now = int(__import__("time").time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        # 获取网页源码
        html = self._fetch(play_page)
        
        # 提取 m3u8
        m3u8 = self._extract_player_url(html) if html else ""
        
        if m3u8:
            self.log("✅ 成功提取到 M3U8: %s" % m3u8)
            
            # 构造终极伪装 Header，欺骗 CDN 防盗链
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": self.site_url + "/",  
                "Origin": self.site_url,
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Connection": "keep-alive"
            }
            
            res = {
                "parse": 0,              # 0 代表直接播放
                "playUrl": "",           # 留空，防止跳转其他源
                "url": m3u8,             # 直链 m3u8
                "header": headers,
            }
            self._play_cache[play_page] = (now, res)
            return res
        else:
            self.log("❌ 未提取到 M3U8，可能被拦截或页面结构改变")
            self.log("网页片段: %s" % html[:200])

        # 兜底：如果真没抓到，返回原播放页让 TVBox 嗅探
        res = {
            "parse": 1, 
            "playUrl": "", 
            "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"}
        }
        self._play_cache[play_page] = (now, res)
        return res

    def _extract_player_url(self, html):
        if not html:
            return ""
        # 精确匹配 player_aaaa
        m = _RE_PLAYER_AA.search(html)
        raw = m.group(1) if m else ""
        
        if not raw:
            # 兜底匹配直接的 m3u8 链接
            m2 = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html, re.I)
            if m2:
                return m2.group(1).replace("\\/", "/").replace("\\u0026", "&")
            return ""

        # 清理转义字符
        raw = raw.replace("\\/", "/").replace("\\u0026", "&").replace("\\u0022", '"')
        try:
            obj = json.loads(raw)
        except Exception as e:
            self.log("JSON 解析失败: %s" % e)
            m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            return m2.group(1) if m2 else ""
            
        url = obj.get("url", "")
        encrypt = obj.get("encrypt", 0)
        
        if encrypt != 0:
            self.log("⚠️ 警告: encrypt=%s 非0，此视频有加密，大概率无法直链播放" % encrypt)
            
        if url.startswith("//"):
            url = "https:" + url
            
        return url

    # ---------- 其他 ----------
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
