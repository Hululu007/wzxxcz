# coding=utf-8
"""
风月影院 www.cqjwny.com | TVBox Python 爬虫
网站结构解析：
  - 列表页：/vodshow/{tid}-----------.html
  - 详情页：/voddetail/{id}.html
  - 播放页：/vodplay/{id}-{sid}-{nid}.html
  - 播放地址：页面内 var player_aaaa={...} 的 url 字段（m3u8 直链）
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
                print("[cqjwny]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.cqjwny.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "20", "type_name": "短剧"},
]


class Spider(Spider):

    def getName(self):
        return "风月影院"

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
        self.log("init site=%s" % self.site_url)

    def log(self, *a, **kw):
        try:
            print("[cqjwny]", *a)
        except Exception:
            pass

    def _fetch(self, url, timeout=15):
        try:
            r = self.fetch(url, headers=self.headers, timeout=timeout)
            if hasattr(r, "text"):
                text = r.text or ""
            elif hasattr(r, "content"):
                text = r.content.decode("utf-8", "ignore")
            else:
                text = str(r)
            return text
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

    # ---------------- 列表解析 ----------------
    def _parse_video_list(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        # 普通列表卡片 / 搜索页 media 卡片 / 首页轮播
        patterns = [
            re.compile(
                r'<a class="stui-vodlist__thumb lazyload" href="(/voddetail/\d+\.html)" '
                r'title="([^"]*)" data-original="([^"]*)"[\s\S]*?</a>', re.S),
            re.compile(
                r'<a class="v-thumb stui-vodlist__thumb lazyload" href="(/voddetail/\d+\.html)" '
                r'title="([^"]*)" data-original="([^"]*)"[\s\S]*?</a>', re.S),
            re.compile(
                r'<a href="(/voddetail/\d+\.html)" class="stui-vodlist__thumb active" '
                r'title="([^"]*)" style="background: url\(([^)]+)\)[\s\S]*?</a>', re.S),
        ]

        for pat in patterns:
            for m in pat.finditer(html):
                href, title, pic = m.group(1), self._clean(m.group(2)), m.group(3)
                if href in seen:
                    continue
                seen.add(href)

                block = m.group(0)
                rem = re.search(r'<span class="pic-text text-right">([^<]*)</span>', block)
                remarks = self._clean(rem.group(1)) if rem else ""
                pic = (pic or "").split("#")[0]

                videos.append({
                    "vod_id": self._fix_url(href),
                    "vod_name": title or href,
                    "vod_pic": self._fix_url(pic),
                    "vod_remarks": remarks,
                })

        # 首页/侧栏文本列表
        for m in re.finditer(
                r'<a class="top-line-dot text-overflow" href="(/voddetail/\d+\.html)" '
                r'title="([^"]*)"><span class="text-muted pull-right">([^<]*)</span>([^<]*)</a>',
                html):
            href, title, remarks, _ = m.groups()
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": self._fix_url(href),
                "vod_name": self._clean(title),
                "vod_pic": "",
                "vod_remarks": self._clean(remarks),
            })

        return videos

    def _page_count(self, html, current=1):
        if not html:
            return current
        m = re.search(r'<span class="num">\d+/(\d+)</span>', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass

        pages = re.findall(r'-------(\d+)---', html)
        nums = []
        for p in pages:
            try:
                nums.append(int(p))
            except Exception:
                pass
        return max(nums + [current]) if nums else current

    # ---------------- 首页 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": {}}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        videos = self._parse_video_list(html)
        return {"list": videos[:60]}

    # ---------------- 分类 ----------------
    def _category_url(self, tid, pg):
        pg = int(pg) if pg else 1
        if pg <= 1:
            return "%s/vodshow/%s-----------.html" % (self.site_url, tid)
        return "%s/vodshow/%s--------%d---.html" % (self.site_url, tid, pg)

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        url = self._category_url(tid, page)
        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._parse_video_list(html)

        # 分页构造失败时，回退到从第一页分页链接里找当前页
        if not videos and page > 1:
            base = "%s/vodshow/%s-----------.html" % (self.site_url, tid)
            base_html = self._fetch(base)
            m = re.search(r'<a href="([^"]+)">%d</a>' % page, base_html)
            if m:
                html = self._fetch(self._fix_url(m.group(1)))
                videos = self._parse_video_list(html)

        pagecount = self._page_count(html, page)
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)

        urls = [
            "%s/vodsearch/%s-------------.html" % (self.site_url, keyword),
            "%s/vodsearch/-------------.html?wd=%s" % (self.site_url, keyword),
        ]

        html = ""
        videos = []
        for url in urls:
            self.log("search: %s" % url)
            html = self._fetch(url)
            videos = self._parse_video_list(html)
            if videos:
                break

        return {
            "list": videos,
            "page": page,
            "pagecount": self._page_count(html, page),
            "limit": 24,
            "total": len(videos),
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 ----------------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}

        vod_id = ids[0]
        url = vod_id if str(vod_id).startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = re.search(r'<h1 class="title">([\s\S]*?)</h1>', html)
        if m:
            name = self._clean(re.sub(
                r'<span class="score[^"]*">[\s\S]*?</span>', '', m.group(1)))
        if not name:
            m = re.search(r'<title>《?([^》<_-]+)', html)
            if m:
                name = self._clean(m.group(1))

        # 封面
        pic = ""
        m = re.search(
            r'<a class="stui-vodlist__thumb picture v-thumb"[\s\S]*?'
            r'<img[^>]*data-original="([^"]*)"', html)
        if m:
            pic = self._fix_url(m.group(1).split("#")[0])

        # 评分 / 备注
        score = ""
        m = re.search(r'<span class="score text-red">([\d.]+)</span>', html)
        if m:
            score = m.group(1)

        remarks = ""
        m = re.search(r'<span class="pic-text text-right">([^<]*)</span>', html)
        if m:
            remarks = self._clean(m.group(1))

        # 简介
        content = ""
        m = re.search(
            r'<div class="stui-pannel stui-pannel-bg clearfix" id="desc">'
            r'[\s\S]*?<p class="col-pd">([\s\S]*?)</p>', html)
        if not m:
            m = re.search(
                r'<p class="desc hidden-xs">[\s\S]*?'
                r'<span class="left text-muted">简介：</span>([\s\S]*?)<a href="#desc">', html)
        if not m:
            m = re.search(r'<meta name="description" content="([^"]*)"', html)
        if m:
            content = self._clean(m.group(1))
        content = INTRO_PREFIX + ("\n" + content if content else "")

        # 主演 / 导演
        actor = ""
        m = re.search(r'<span class="text-muted">主演：</span>([\s\S]*?)</p>', html)
        if m:
            actor = self._clean(m.group(1))

        director = ""
        m = re.search(r'<span class="text-muted">导演：</span>([\s\S]*?)</p>', html)
        if m:
            director = self._clean(m.group(1))

        # 剧集线路：解析每个 <div class="stui-pannel-box b playlist mb"> 下的 h3 + playlist
        play_from = []
        play_url = []

        playlist_pat = re.compile(
            r'<div class="stui-pannel-box b playlist mb">[\s\S]*?'
            r'<h3 class="title">([\s\S]*?)</h3>[\s\S]*?'
            r'<ul class="stui-content__playlist clearfix">([\s\S]*?)</ul>',
            re.S)

        groups = []
        for m in playlist_pat.finditer(html):
            line_name = self._clean(m.group(1)) or ("线路%d" % (len(groups) + 1))
            groups.append((line_name, m.group(2)))

        if not groups:
            for ul in re.findall(
                    r'<ul class="stui-content__playlist clearfix">([\s\S]*?)</ul>',
                    html, re.S):
                groups.append(("线路%d" % (len(groups) + 1), ul))

        for line_name, ul in groups:
            eps = []
            for em in re.finditer(r'<a href="([^"]+)">([^<]+)</a>', ul):
                href = self._fix_url(em.group(1).replace("&amp;", "&"))
                ep_name = self._clean(em.group(2))
                eps.append("%s$%s" % (ep_name, href))
            if eps:
                play_from.append(line_name)
                play_url.append("#".join(eps))

        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name or vod_id,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if str(id).startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        html = self._fetch(play_page)
        if not html:
            return {
                "parse": 1,
                "playUrl": "",
                "url": play_page,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }

        # 播放页核心：var player_aaaa={...}
        m = re.search(r'var player_aaaa=(\{[\s\S]*?\})\s*</script>', html)
        if not m:
            m = re.search(r'var player_aaaa=(\{[\s\S]*?\});', html)

        if m:
            raw = m.group(1)
            url = ""
            try:
                data = json.loads(raw)
                url = data.get("url", "")
            except Exception:
                um = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                url = um.group(1) if um else ""

            if url:
                url = (url.replace("\\/", "/")
                          .replace("\\u0026", "&")
                          .replace("&amp;", "&"))
                if url.startswith("//"):
                    url = "https:" + url

                self.log("play url: %s" % url[:200])
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": url,
                    "header": {
                        "User-Agent": UA,
                        "Referer": play_page,
                    },
                }

        # 兜底交给 TVBox 嗅探
        return {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
