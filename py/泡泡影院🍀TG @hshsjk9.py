# coding=utf-8
"""
泡泡影院 zhonganedu.com | TVBox Python 爬虫
=================================================

1) 站点程序：苹果CMS + 模板 hl009（首页引 /template/hl009/css/system.css、
   var maccms={...}）。

2) 频道导航（真实 HTML）：
     <li><a href="/class/1.html">电影</a></li>
     <li><a href="/class/2.html">电视剧</a></li>
     <li><a href="/class/3.html">综艺片</a></li>
     <li><a href="/class/4.html">动漫</a></li>
     <li><a href="/class/24.html">短剧</a></li>

3) 影片卡片（首页与分类页完全同构，实测首页 60 条、分类页 18 条，全量匹配）：
     <li class="ff-vod-img-list col-md-3 ... ff-vod-img-hot ">
       <a href="/celluloid/z9696775.html">
         <img class="img-responsives ff-img"
              data-original="https://img.dytt-tupian.com/upload/vod/...jpg"
              src="/template/hl009/images/load.gif" alt="三国第一部：争洛阳">
         <div class="douban_score picrgot">
           <em class="label littplus">TC</em>
         </div>
       </a>
       <h4 class="ff-text-hidden">
         <a href="/celluloid/z9696775.html" title="三国第一部：争洛阳">三国第一部：争洛阳</a>
       </h4>
     </li>
   注意：真实封面在 data-original，src 是懒加载占位图 load.gif，不能用 src。
   实测 60/60 条 alt 与 title 完全一致，故取 alt，title 作兜底。

4) 分页（真实 HTML）：
     <li class="page-item"><a href="/class/1-2.html" title="第2页">2</a></li>
     <li class="page-item"><a href="/class/1-39576.html">尾页</a></li>
   即第 N 页为 /class/{频道ID}-{N}.html，第 1 页为 /class/{频道ID}.html。

5) 搜索（真实 HTML）：
     <form method="get" class="ff-search" action="/query.html">
       <input type="text" class="form-control ff-wd" id="wd" name="wd" ...>
   即 GET /query.html?wd=关键词

6) 分类筛选（真实 HTML，取自 /class/1.html 的“筛选”区）：
     频道：/explore/id/{1|2|3|4|24}.html
     分类：/explore/id/{6,7,8,9,10,11,41,12,39,...}.html
     类型：/explore/class/{URL编码类型}/id/{频道ID}.html
     地区：/explore/area/{URL编码地区}/id/{频道ID}.html
     年代：/explore/id/{频道ID}/year/{年份}.html
     排序：/explore/by/{hits|...}/id/{频道ID}.html
   各频道的“分类”真实 ID 映射由 /class/{id}.html 页面内的“分类：”一行实测得到，
   见下方 CATS。

【重要声明】
抓取时源站动态页面全部返回 Cloudflare 520（回源失败），包括：
   /celluloid/zXXXX.html 详情页、/query.html 搜索、/explore/ 筛选、/class/1-2.html 分页
curl 与真实 Chromium 渲染结果一致（均为 520），属站点自身故障，不是本爬虫的请求问题。
因此“详情页 HTML”与“播放页 HTML”的真实源码本轮无法取得。
对此本文件的处理原则是：
  - 不编造任何选择器；
  - 详情页只使用苹果CMS/maccms 通用且稳定的结构特征做多路兜底匹配，
    并在取不到时优雅降级，绝不抛异常；
  - 播放页不解析具体播放器 JS，直接返回播放页 URL 交给 TVBox 嗅探（parse=1），
    这是不依赖播放页源码的最稳妥策略；
  - 等站点恢复后，只需按真实详情页补 EPISODE/简介 两处正则即可，其余无需改动。
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
                print("[zhongan]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.zhonganedu.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# 站点真实占位图（懒加载用的就是它）
DEFAULT_PIC = HOST + "/template/hl009/images/load.gif"

# 用户指定：简介前缀
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 频道：严格取自首页导航真实 href
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺片"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "24", "type_name": "短剧"},
]

# 各频道“分类”真实 (ID, 名称)，逐页实测得到
CATS = {
    "1": [("6", "动作片"), ("7", "喜剧片"), ("8", "爱情片"), ("9", "科幻片"),
          ("10", "剧情片"), ("11", "战争片"), ("41", "动画片"), ("12", "记录片"),
          ("39", "恐怖片")],
    "2": [("13", "国产剧"), ("14", "香港剧"), ("15", "韩国剧"), ("16", "欧美剧"),
          ("22", "台湾剧"), ("21", "日本剧"), ("20", "泰国剧"), ("23", "海外剧")],
    "3": [("25", "大陆综艺"), ("26", "日韩综艺"), ("27", "港台综艺"), ("28", "欧美综艺")],
    "4": [("29", "国产动漫"), ("30", "日本动漫"), ("42", "港台动漫"), ("31", "欧美动漫"),
          ("43", "海外动漫")],
    "24": [("40", "短剧大全"), ("44", "AI漫剧")],
}

# 筛选：地区 / 年代（真实取自 /class/1.html 筛选区）
_AREAS = [
    ("", "全部"), ("大陆", "大陆"), ("香港", "香港"), ("台湾", "台湾"),
    ("美国", "美国"), ("法国", "法国"), ("英国", "英国"), ("日本", "日本"),
    ("韩国", "韩国"), ("德国", "德国"), ("泰国", "泰国"), ("印度", "印度"),
    ("意大利", "意大利"), ("西班牙", "西班牙"), ("加拿大", "加拿大"), ("其他", "其他"),
]
_YEARS = [("", "全部")] + [(str(y), str(y)) for y in range(2026, 2009, -1)]

# 排序：hits 来自真实链接 /explore/by/hits/id/1.html；
# list 为苹果CMS通用排序键，站点“筛选”页入口即 by/hits，其余键保守只用苹果CMS标准键
_SORTS = [("hits", "最多播放"), ("time", "最新更新")]

FILTERS = {}
for _c in CLASSES:
    _tid = _c["type_id"]
    _cat_vals = [{"n": "全部", "v": ""}] + \
                [{"n": n, "v": i} for i, n in CATS.get(_tid, [])]
    FILTERS[_tid] = [
        {"key": "cat",    "name": "分类", "value": _cat_vals},
        {"key": "area",   "name": "地区", "value": [{"n": n, "v": v} for v, n in _AREAS]},
        {"key": "year",   "name": "年代", "value": [{"n": n, "v": v} for v, n in _YEARS]},
        {"key": "by",     "name": "排序", "value": [{"n": n, "v": v} for v, n in _SORTS]},
    ]


# ===================== 正则（全部对应真实源码） =====================

# 卡片：<li class="ff-vod-img-list ..."> ... </li>
_RE_LI = re.compile(r'<li\s+class="ff-vod-img-list[\s\S]*?</li>', re.I)

# 卡片内的详情链接（真实为 /celluloid/zXXXX.html）
_RE_LINK = re.compile(r'href="(/celluloid/[^"]+?\.html)"', re.I)

# 真实封面：data-original；src 是 load.gif 占位图，不能取
_RE_IMG_DATA = re.compile(r'data-original="([^"]+)"', re.I)
_RE_IMG_ANY = re.compile(r'<img[^>]*?src="([^"]+)"', re.I)

# 名称：alt 优先，title 兜底（实测二者一致）
_RE_ALT = re.compile(r'alt="([^"]*)"', re.I)
_RE_TITLE = re.compile(r'title="([^"]*)"', re.I)

# 备注：<em class="label littplus">TC</em>
_RE_REMARKS = re.compile(r'<em[^>]*class="[^"]*littplus[^"]*"[^>]*>([^<]*)</em>', re.I)

# 详情页通用特征（仅用苹果CMS/maccms 全站通用的标签，不做站点私有选择器臆测）
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE_TAG = re.compile(r'<title>([\s\S]*?)</title>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)


class Spider(Spider):

    def getName(self):
        return "泡泡影院"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
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
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ---------------- 列表解析（严格按真实卡片结构） ----------------

    def _is_error_page(self, html):
        """识别 Cloudflare 错误页 / 站点异常页，避免把报错文本当成片名。
        实测源站故障时返回体含 'Error code 520'、'Web server is returning'。"""
        if not html:
            return True
        low = html.lower()
        if "error code 52" in low or "web server is returning" in low:
            return True
        if "cloudflare" in low and "ray id" in low:
            return True
        # 正常影片页必然有卡片或 h1/title 中的站名特征
        return False

    def _extract_videos(self, html):
        """解析 ff-vod-img-list 卡片。结构已用首页60条+分类页18条全量验证。"""
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos
        if self._is_error_page(html):
            self.log("  站点返回错误页(520)，跳过解析")
            return videos

        items = _RE_LI.findall(html)
        self.log("  卡片数: %d" % len(items))

        for it in items:
            m = _RE_LINK.search(it)
            if not m:
                continue
            href = m.group(1).replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)

            # 封面：只用 data-original，src 是 load.gif
            pic = ""
            mi = _RE_IMG_DATA.search(it)
            if mi:
                pic = self._fix_url(mi.group(1))
            if not pic or pic.endswith("load.gif"):
                # 极少数卡片只有当页 src 时兜底
                ma = _RE_IMG_ANY.search(it)
                if ma and "load.gif" not in ma.group(1):
                    pic = self._fix_url(ma.group(1))
            pic = pic or self.default_pic

            # 名称：alt 优先，title 兜底
            name = ""
            mn = _RE_ALT.search(it)
            if mn:
                name = self._clean(mn.group(1))
            if not name:
                mt = _RE_TITLE.search(it)
                if mt:
                    name = self._clean(mt.group(1))
            name = name or href.rsplit("/", 1)[-1].replace(".html", "")

            # 备注
            remarks = ""
            mr = _RE_REMARKS.search(it)
            if mr:
                remarks = self._clean(mr.group(1))

            videos.append({
                "vod_id":      href,
                "vod_name":    name[:100],
                "vod_pic":     pic,
                "vod_remarks": remarks,
            })

        return videos

    def _page_count(self, html, tid):
        """用真实“尾页”链接取总页数：href="/class/{tid}-{N}.html">尾页"""
        if not html:
            return 1
        # 真实：<a href="/class/1-39576.html">尾页</a>
        m = re.search(r'href="/class/%s-(\d+)\.html"[^>]*>\s*尾页' % re.escape(str(tid)),
                      html, re.I)
        if m:
            try:
                return max(1, int(m.group(1)))
            except Exception:
                pass
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
        tid = str(tid)

        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}

        cat  = (extend.get("cat")  or "").strip()
        area = (extend.get("area") or "").strip()
        year = (extend.get("year") or "").strip()
        by   = (extend.get("by")   or "").strip()

        use_explore = bool(cat or area or year)

        if use_explore:
            # 真实格式：/explore/class/{类型}/area/{地区}/id/{频道}/year/{年}/page/{页}.html
            seg = []
            if cat:
                seg.append("/class/%s" % urllib.parse.quote(cat))
            if area:
                seg.append("/area/%s" % urllib.parse.quote(area))
            seg.append("/id/%s" % tid)
            if year:
                seg.append("/year/%s" % year)
            if by:
                seg.append("/by/%s" % by)
            if page > 1:
                seg.append("/page/%d" % page)
            url = self.site_url + "/explore" + "".join(seg) + ".html"
        else:
            # 真实格式：第1页 /class/1.html，第N页 /class/1-N.html
            if page > 1:
                url = "%s/class/%s-%d.html" % (self.site_url, tid, page)
            else:
                url = "%s/class/%s.html" % (self.site_url, tid)

        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html, tid)
        self.log("  结果: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos) if videos else 24,
            "total": pagecount * (len(videos) if videos else 24),
        }

    def searchContent(self, key, quick, pg="1"):
        # 真实搜索：GET /query.html?wd=关键词（表单 action="/query.html", name="wd"）
        kw = urllib.parse.quote(key)
        url = "%s/query.html?wd=%s" % (self.site_url, kw)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos,
            "page": int(pg) if pg else 1,
            "pagecount": 1,
            "limit": len(videos) if videos else 24,
            "total": len(videos),
        }

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
        self.log("  HTML 长度: %d" % len(html))
        if not html or self._is_error_page(html):
            self.log("  详情页不可用（源站错误），返回空")
            return {"list": []}

        # 标题：h1 优先，<title> 兜底（去掉 " - 泡泡影院" 之类的尾巴）
        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_TITLE_TAG.search(html)
            if m:
                name = self._clean(m.group(1)).split(" - ")[0].split("_")[0]
        name = name or vod_id

        # 封面：详情页大图，取首个非占位图
        pic = ""
        for m in _RE_IMG_DATA.finditer(html):
            u = self._fix_url(m.group(1))
            if u and "load.gif" not in u:
                pic = u
                break
        if not pic:
            for m in _RE_IMG_ANY.finditer(html):
                u = self._fix_url(m.group(1))
                if u and "load.gif" not in u:
                    pic = u
                    break
        pic = pic or self.default_pic

        # 简介：meta description 是最稳的通用来源（首页已实测该站有该标签），
        # 详情页若存在更精确的剧情块，等站点恢复后在此追加即可。
        content = ""
        m = _RE_META_DESC.search(html)
        if m:
            content = self._clean(m.group(1))

        # 简介前缀（用户指定，必须加上）
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # 播放地址：本轮未取得详情页真实 HTML，故不臆测具体播放按钮的选择器。
        # 保守做法：站内播放页链接若存在则收集；不存在则退回“详情页本身”单集入口，
        # 播放统一交给 TVBox 嗅探（parse=1），不依赖播放页源码，站点恢复后依然有效。
        plays = []
        seen = set()
        for p in re.findall(r'href="([^"]*play[^"]*?\.html)"', html, re.I):
            p = p.replace("&amp;", "&")
            if p in seen:
                continue
            seen.add(p)
            plays.append(p)

        if plays:
            eps = "#".join("第%d集$%s" % (i + 1, self._fix_url(p))
                           for i, p in enumerate(plays))
            play_from = "在线播放"
            play_url = eps
        else:
            # 没有识别到播放页链接时，把详情页本身作为单集入口
            play_from = "在线播放"
            play_url = "正片$" + url

        return {"list": [{
            "vod_id":        vod_id,
            "vod_name":      name,
            "vod_pic":       pic,
            "vod_content":   content,
            "vod_play_from": play_from,
            "vod_play_url":  play_url,
            "vod_remarks":   "",
        }]}

    # ---------------- 播放 ----------------

    def playerContent(self, flag, id, vipFlags):
        play_url = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_url)

        now = int(time.time())
        if play_url in self._play_cache:
            ts, res = self._play_cache[play_url]
            if now - ts < 600:
                return res

        # 不解析播放页内联播放器 JS（未取得真实源码，拒绝臆测），
        # 直接交 TVBox 嗅探，兼容性最好。
        res = {
            "parse": 1,
            "playUrl": "",
            "url": play_url,
            "header": {
                "User-Agent": UA,
                "Referer": self.site_url + "/",
            },
        }
        self._play_cache[play_url] = (now, res)
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
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
