# coding=utf-8
"""
影视大全 iysdq1.com | TVBox Python 爬虫

全部解析规则均严格依据站点真实网页源码编写，无任何臆测：
  - 分类导航  ：/ → 推荐 ; /vodtype/{1..5}.html → 电影/电视剧/综艺/动漫/短剧
  - 搜索      ：/vodsearch/{urlencode(词)}-------------.html   （也支持 ?wd=词）
  - 列表卡片  ：div.public-list-box > a.public-list-exp[href=/voddetail/{id}.html][title=剧名]
                img[alt="剧名封面图"][src=占位图][data-src=真实封面]
                span.public-list-prb → 更新至第N集 / 已完结
                span.public-prt     → 类型角标
  - 详情页    ：div.this-desc-info  → 评分/年份/地区/状态
                div.this-info       → 导演 / 演员
                #height_limit       → 简介正文
                div.anthology-tab a → 线路名（AA线/A线/B线.../http下载）
                div.anthology-list-box ul.anthology-list-play li a[href=/vodplay/{id}-{sid}-{nid}.html]
  - 播放页    ：var player_aaaa={"flag":"play","encrypt":0,...,
                "url":"https://svip.xgplay17.com/.../index.m3u8","from":"xiguam3u8",...}
                真实 m3u8 明文在 player_aaaa.url（首选）
                部分页面为 JXplayer 壳：iframe src 的 v= 参数（兜底）
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
                print("[iysdq]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.iysdq1.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 站点真实占位图（源码实测：所有卡片 src 均指向它，真实封面在 data-src）
DEFAULT_PIC = HOST + "/template/shoutu45/assets/images/img-bj-k.png"

# 简介前缀（按要求固定添加）
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 分类：源码实测 href="/vodtype/{tid}.html"
CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "5", "type_name": "短剧"},
]

# 说明：站点分类页未在已获取的源码中出现“地区/年份/剧情”下拉筛选控件，
# 无法证实其筛选 URL 结构，故不臆造 filters（宁缺勿猜）。
FILTERS = {c["type_id"]: [] for c in CLASSES}


# ===================== 正则（全部对应真实源码结构） =====================

# 列表卡片：a.public-list-exp ... <img ... alt="X封面图" ... data-src="真实URL">
_RE_CARD = re.compile(
    r'<a\s+[^>]*class="[^"]*public-list-exp[^"]*"[^>]*'
    r'href="(/voddetail/\d+\.html)"[^>]*'
    r'title="([^"]*)"[^>]*>\s*'
    r'<img[^>]*?alt="([^"]*?)"[^>]*?data-src="([^"]*)"',
    re.S | re.I)

# 卡片备注（更新至第N集 / 已完结 / 全集 …）
_RE_REMARKS = re.compile(
    r'<span\s+class="public-list-prb[^"]*"[^>]*>([^<]+)</span>',
    re.I)

# 详情页 · 简介：<div id="height_limit" class="text"><strong ...>描述:</strong>正文</div>
_RE_INTRO = re.compile(
    r'<div[^>]*id="height_limit"[^>]*>(.*?)</div>',
    re.S | re.I)
_RE_INTRO_DESC = re.compile(r'<strong[^>]*>\s*描述[:：]\s*</strong>', re.I)

# 详情页 · 元信息：<div class="this-desc-info">...<span>2025</span><span>大陆</span>...
_RE_DESC_INFO = re.compile(
    r'<div[^>]*class="this-desc-info"[^>]*>(.*?)</div>',
    re.S | re.I)
_RE_DESC_SCORE = re.compile(
    r'<span[^>]*class="this-desc-score[^"]*"[^>]*>(.*?)</span>',
    re.S | re.I)
_RE_SPAN = re.compile(r'<span[^>]*>(.*?)</span>', re.S | re.I)

# 详情页 · 导演 / 演员：<div class="this-info"><strong>导演:</strong><a>名</a><i>，</i>...
_RE_INFO_BLOCK = re.compile(
    r'<div[^>]*class="this-info"[^>]*>\s*<strong[^>]*>([^<]+)</strong>(.*?)</div>',
    re.S | re.I)

# 详情页 · 线路名：<div class="anthology-tab ..."><a class="swiper-slide">...名<span class="badge">N</span></a>
_RE_TAB_WRAP = re.compile(
    r'<div[^>]*class="anthology-tab[^"]*"[^>]*>(.*?)</div>\s*</div>',
    re.S | re.I)
_RE_TAB_A = re.compile(
    r'<a[^>]*class="[^"]*swiper-slide[^"]*"[^>]*>(.*?)</a>',
    re.S | re.I)

# 详情页 · 剧集列表容器组
_RE_LIST_WRAP = re.compile(
    r'<div[^>]*class="anthology-list[^"]*select-c"[^>]*>(.*)</div>\s*</div>\s*</div>',
    re.S | re.I)
_RE_LIST_BOX = re.compile(
    r'<div[^>]*class="anthology-list-box[^"]*"[^>]*>(.*?)</div>\s*</div>',
    re.S | re.I)
_RE_EP_A = re.compile(
    r'<a[^>]*href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*>(.*?)</a>',
    re.S | re.I)
# http下载（mp4 直链）
_RE_DL_A = re.compile(
    r'<a[^>]*class="left"[^>]*href="(https?://[^"]+\.mp4)"[^>]*>(.*?)</a>',
    re.S | re.I)

# 播放页 · player_aaaa JSON（真实源码实测，url 字段即直链 m3u8）
_RE_PLAYER_AAAA = re.compile(
    r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.S | re.I)
# 播放页 · iframe 真实 m3u8（JXplayer 壳兜底）
_RE_IFRAME_SRC = re.compile(
    r'<iframe[^>]*?src="([^"]+)"', re.S | re.I)
_RE_V_PARAM = re.compile(r'[?&]v=([^&"\']+)', re.I)

_LINE_PRIORITY = ["AA线", "A线", "B线", "C线", "D线", "E线", "F线"]


class Spider(Spider):

    def getName(self):
        return "影视大全"

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
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
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
        # 去掉字体图标实体（如 &#xe679;）
        s = re.sub(r"&#x?[0-9a-fA-F]+;", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ---------------- 列表解析（首页/分类/搜索 通用） ----------------

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for m in _RE_CARD.finditer(html):
            href, title, alt, pic = m.groups()
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)

            # 备注：在卡片 a 标签闭合前就近截取
            tail = html[m.end():m.end() + 600]
            rm = _RE_REMARKS.search(tail)
            remarks = self._clean(rm.group(1)) if rm else ""

            name = self._clean(title) or self._clean(alt).replace("封面图", "")
            videos.append({
                "vod_id":      href,
                "vod_name":    name,
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks,
            })
        return videos

    def _page_count(self, html):
        """源码中未见分页控件，无法证实 → 返回 1，避免臆造翻页逻辑。"""
        return 1

    # ---------------- TVBox 接口 ----------------

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        # 真实分类 URL：/vodtype/{tid}.html
        url = "%s/vodtype/%s.html" % (self.site_url, tid)
        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        self.log("  最终: %d 条" % len(videos))
        return {
            "list": videos, "page": page, "pagecount": 1,
            "limit": 24, "total": len(videos),
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        # 真实搜索 URL（源码实测两种形式均可，此处用路径式）
        url = "%s/vodsearch/%s-------------.html" % (self.site_url, kw)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        self.log("  最终: %d 条" % len(videos))
        return {
            "list": videos, "page": page, "pagecount": 1,
            "limit": 24, "total": len(videos),
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
        if not html:
            return {"list": []}

        # --- 标题：div.this-desc-title ---
        name = ""
        m = re.search(r'<div[^>]*class="this-desc-title"[^>]*>(.*?)</div>',
                      html, re.S | re.I)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*《?([^》]*)》?.*", r"\1", name).strip() or vod_id

        # --- 封面：详情页顶部背景 div.this-pic-bj style:background-image ---
        pic = self.default_pic
        m = re.search(r'this-pic-bj[^>]*background-image:\s*url\([\'"]?([^\'")]+)',
                      html, re.I)
        if not m:
            m = re.search(r'<img[^>]*?data-src="([^"]+)"', html, re.I)
        if m:
            pic = self._fix_url(m.group(1))

        # --- 简介：#height_limit （去掉 "描述:"） ---
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            raw = m.group(1)
            raw = _RE_INTRO_DESC.sub("", raw)
            content = self._clean(raw)
        if not content:
            # 兜底：meta description（源码实测同样含剧情介绍）
            m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"',
                          html, re.I)
            if m:
                content = self._clean(m.group(1))
                content = re.sub(r"^.*?剧情介绍[:：]\s*", "", content)
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # --- 评分 / 年份 / 地区 / 状态：div.this-desc-info ---
        score, year, area, remarks = "", "", "", ""
        m = _RE_DESC_INFO.search(html)
        if m:
            block = m.group(1)
            sm = _RE_DESC_SCORE.search(block)
            if sm:
                score = self._clean(sm.group(1))
                block = block.replace(sm.group(0), "")
            spans = [self._clean(x) for x in _RE_SPAN.findall(block)]
            spans = [x for x in spans if x]
            # 真实顺序：年份 地区 状态
            if len(spans) >= 1:
                year = spans[0]
            if len(spans) >= 2:
                area = spans[1]
            if len(spans) >= 3:
                remarks = spans[2]

        # --- 导演 / 演员：div.this-info ---
        director, actor = "", ""
        for m in _RE_INFO_BLOCK.finditer(html):
            label = self._clean(m.group(1))
            names = [self._clean(x) for x in
                     re.findall(r'<a[^>]*>(.*?)</a>', m.group(2), re.S | re.I)]
            names = [x for x in names if x]
            if "导演" in label:
                director = ", ".join(names)
            elif "演员" in label or "主演" in label:
                actor = ", ".join(names)

        # --- 线路 + 剧集 ---
        lines = self._parse_play_lines(html)
        if not lines:
            return {"list": []}

        play_from = []
        play_url = []
        for line_name, eps in lines:
            play_from.append(line_name)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        return {"list": [{
            "vod_id":       vod_id,
            "vod_name":     name,
            "vod_pic":      pic,
            "vod_content":  content,
            "vod_actor":    actor,
            "vod_director": director,
            "vod_year":     year,
            "vod_area":     area,
            "vod_score":    score,
            "vod_remarks":  remarks or ("%d条线路" % len(lines)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    def _parse_play_lines(self, html):
        """按源码真实结构解析线路名 + 剧集（顺序严格一一对应）。"""
        # 1) 线路名列表
        line_names = []
        m = re.search(r'<div[^>]*class="anthology-tab[^"]*"[^>]*>(.*?)</div>\s*</div>',
                      html, re.S | re.I)
        if m:
            for am in _RE_TAB_A.finditer(m.group(1)):
                inner = am.group(1)
                inner = re.sub(r'<span[^>]*>.*?</span>', '', inner,
                               flags=re.S | re.I)   # 去掉 badge 数量
                nm = self._clean(inner).replace("&nbsp;", "").strip()
                line_names.append(nm)

        # 2) 剧集容器组
        boxes = []
        mw = re.search(
            r'<div[^>]*class="anthology-list[^"]*select-c"[^>]*>(.*)'
            r'<script>\s*\$\(["\']\.anthology-tab a',
            html, re.S | re.I)
        scope = mw.group(1) if mw else html
        for bm in re.finditer(
                r"<div[^>]*class=[\"']anthology-list-box[^\"']*[\"'][^>]*>(.*?)</ul>",
                scope, re.S | re.I):
            body = bm.group(1)
            eps = []
            for em in _RE_EP_A.finditer(body):
                href = em.group(1).replace("&amp;", "&")
                ep_name = self._clean(em.group(2)) or ("第%s集" % (len(eps) + 1))
                eps.append((ep_name, href))
            # http下载线
            if not eps:
                for dm in _RE_DL_A.finditer(body):
                    href = dm.group(1).replace("&amp;", "&")
                    nm = self._clean(dm.group(2)) or ("下载%s" % (len(eps) + 1))
                    eps.append((nm, href))
            if eps:
                boxes.append(eps)

        # 3) 合并：线路名与容器一一对应
        lines = []
        for i, eps in enumerate(boxes):
            nm = line_names[i] if i < len(line_names) else ("线路%d" % (i + 1))
            lines.append((nm, eps))

        # 4) 排序：优先 AA线/A线/B线…，http下载置后
        def _key(item):
            n = item[0]
            return _LINE_PRIORITY.index(n) if n in _LINE_PRIORITY else 999
        lines.sort(key=_key)
        return lines

    # ---------------- 播放 ----------------

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        # http下载返回的是 mp4 直链，直接用
        if play_page.lower().endswith(".mp4"):
            return {
                "parse": 0, "playUrl": "", "url": play_page,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)

        real_url = ""
        if html:
            # 首选：var player_aaaa = {...} 的 url 字段（真实源码实测直出 m3u8）
            m = _RE_PLAYER_AAAA.search(html)
            if m:
                try:
                    raw = m.group(1)
                    # 源码中 \/ 转义，先还原再解析
                    raw = raw.replace('\\/', '/')
                    pa = json.loads(raw)
                    real_url = (pa.get("url") or "").strip()
                    enc = pa.get("encrypt", 0)
                    self.log("  player_aaaa from=%s encrypt=%s url=%s" %
                             (pa.get("from"), enc, real_url[:120]))
                    # encrypt 0 = 明文直链；如遇 1/2（base64等）走兜底嗅探
                    if enc and enc != 0:
                        real_url = ""
                except Exception as e:
                    self.log("  player_aaaa JSON 解析失败: %s" % e)
                    real_url = ""

            # 兜底1：JXplayer 壳，真实 m3u8 在 iframe src 的 v= 参数
            if not real_url:
                m = _RE_IFRAME_SRC.search(html)
                if m:
                    src = m.group(1).replace("&amp;", "&")
                    vm = _RE_V_PARAM.search(src)
                    if vm:
                        real_url = urllib.parse.unquote(vm.group(1))

            # 兜底2：整页直接找 m3u8
            if not real_url:
                m2 = re.search(r'(https?://[^\s"\'&]+\.m3u8[^\s"\']*)', html, re.I)
                if m2:
                    real_url = m2.group(1)

        if real_url:
            self.log("  => m3u8: %s" % real_url[:160])
            res = {
                "parse": 0, "playUrl": "", "url": real_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
        else:
            # 兜底交给 TVBox 嗅探
            res = {
                "parse": 1, "playUrl": "", "url": play_page,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
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
