# coding=utf-8
"""
水牛影院 sunnykings.com | TVBox Python 爬虫
网站基于 MacCMS 模板 (stui / mb13)
URL 规则:
  首页: /
  分类列表: /listnew/{type_id}.html  第2页: /listnew/{type_id}-{page}.html
  详情页: /{模块}/{vod_id}.html  (模块: weihu电影 / wap综艺 / cp电视剧 / dsj短剧 / dm动漫 / dl电影)
  播放页: /tvplay/{vod_id}-{sid}-{nid}.html   或  /tvplay/{key}.html
  搜索: POST /search/-------------.html  参数 wd=关键词
  搜索第N页: GET /search/{关键词}----------{page}---.html
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
                print("[buffalo]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.sunnykings.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/default18/template/mb13/statics/img/load.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 导航分类
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "30", "type_name": "短剧"},
    {"type_id": "36", "type_name": "伦理片"},
]

# 子分类（按一级分类 tid 对应）
FILTERS = {
    "1": [
        {"key": "class", "name": "类型", "value": [
            {"n": "全部", "v": ""},
            {"n": "动作片", "v": "7"},
            {"n": "喜剧片", "v": "8"},
            {"n": "爱情片", "v": "9"},
            {"n": "科幻片", "v": "10"},
            {"n": "恐怖片", "v": "11"},
            {"n": "剧情片", "v": "12"},
            {"n": "战争片", "v": "13"},
            {"n": "国产剧", "v": "14"},
        ]},
    ],
}


# ===================== 正则 =====================

# 卡片匹配: stui-vodlist__box 里的 thumb
_RE_THUMB_A = re.compile(
    r'<a\s+class=\"[^\"]*stui-vodlist__thumb[^\"]*\"'
    r'[\s\S]*?href=\"([^\"]+)\"[\s\S]*?title=\"([^\"]*)\"[\s\S]*?'
    r'(?:data-original|src)=\"([^\"]*)\"',
    re.S | re.I)

# 备用: 宽松匹配
_RE_THUMB_B = re.compile(
    r'<a[^>]*href=\"(/(?:weihu|wap|cp|dsj|dm|dl|video|vod)/\d+\.html)\"'
    r'[^>]*title=\"([^\"]*)\"[^>]*>[\s\S]{0,300}?'
    r'(?:data-original|src)=\"([^\"]*)\"',
    re.S | re.I)

# 详情页
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)

_RE_DIRECTOR = re.compile(
    r'>导演[：:]\s*</span>([\s\S]*?)</p>', re.I)
_RE_ACTOR = re.compile(
    r'>主演[：:]\s*</span>([\s\S]*?)</p>', re.I)
_RE_TYPE = re.compile(
    r'>类型[：:]\s*</span>([\s\S]*?)</p>', re.I)
_RE_AREA = re.compile(
    r'>地区[：:]\s*</span>([\s\S]*?)</p>', re.I)
_RE_YEAR = re.compile(
    r'>年份[：:]\s*</span>([\s\S]*?)</p>', re.I)
_RE_UPDATE = re.compile(
    r'>更新[：:]\s*([\s\S]{0,30}?)</p>', re.I)
_RE_SCORE = re.compile(r'id=\"score\"[^>]*>[\s\S]*?([\d.]+)\s*<', re.I)
_RE_SCORE_NUM = re.compile(r'([\d.]+)\s*<span\s+class', re.I)

# 简介
_RE_INTRO = re.compile(
    r'<span[^>]*>\s*简介[：:]\s*</span>([\s\S]*?)</div>',
    re.S | re.I)
_RE_INTRO_CONTAINER = re.compile(
    r'class=\"[^\"]*vod_content[^\"]*\"[^>]*>([\s\S]*?)</div>',
    re.S | re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=[\"\']description[\"\'][^>]*content=[\"\']([^\"\']*)[\"\']',
    re.I)

# 线路 + 剧集 (stui-pannel__head 是线路名, 紧跟的 stui-content__playlist 是集数)
# 先获取所有 stui-pannel 块 (每个块 = 一个线路)
_RE_PANNEL_BLOCK = re.compile(
    r'<div\s+class=\"[^\"]*stui-pannel[^\"]*\"[^>]*>([\s\S]*?)'
    r'(?:</div>\s*</div>\s*<div\s+class=\"[^\"]*stui-pannel|$)',
    re.S | re.I)

_RE_LINE_NAME = re.compile(
    r'stui-pannel__head[^>]*>([\s\S]{0,300}?)</div>',
    re.S | re.I)

_RE_PLAYLIST = re.compile(
    r'<ul\s+class=\"[^\"]*stui-content__playlist[^\"]*\"[^>]*>'
    r'([\s\S]*?)</ul>',
    re.S | re.I)

_RE_EPISODE = re.compile(
    r'<li><a\s+href=\"([^\"]+)\"[^>]*>([^<]*)</a></li>',
    re.S | re.I)

# 播放页 player_aaaa
def _parse_player_json(html):
    """解析 player_aaaa JSON, 返回 dict 或 None"""
    idx = html.find("player_aaaa")
    if idx < 0:
        return None
    start = html.find("{", idx)
    if start < 0:
        return None
    # 找到匹配的 }
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
                    break
        pos += 1
    else:
        return None

    try:
        return json.loads(raw)
    except Exception:
        return None


class Spider(Spider):

    def getName(self):
        return "水牛影院"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": ("text/html,application/xhtml+xml,application/xml;"
                       "q=0.9,image/avif,image/webp,*/*;q=0.8"),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # -------- 基础工具 --------
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
        # 解码 HTML 实体 (十进制和十六进制)
        s = re.sub(r'&#(\d+);',
                   lambda m: chr(int(m.group(1))) if int(m.group(1)) < 0x110000 else m.group(0), s)
        s = re.sub(r'&#x([0-9a-fA-F]+);',
                   lambda m: chr(int(m.group(1), 16)) if int(m.group(1), 16) < 0x110000 else m.group(0), s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _extract_videos(self, html):
        """从列表页 HTML 提取视频卡片"""
        videos = []
        seen = set()
        if not html:
            return videos

        # 直接用 stui-vodlist__box 作为分隔标记, 每次取到下一个 box 之前
        blocks = []
        pattern = r'class=\"[^\"]*stui-vodlist__box[^\"]*\"[^>]*>'
        positions = [m.start() for m in re.finditer(pattern, html)]
        for i, pos in enumerate(positions):
            end = positions[i + 1] if i + 1 < len(positions) else pos + 3000
            blocks.append(html[pos:end])

        self.log("  box 块: %d 个" % len(blocks))

        for block in blocks:
            # 提取 thumb 的 href
            href = ""
            href_m = re.search(
                r'<a\s+[^>]*class=\"[^\"]*stui-vodlist__thumb[^\"]*\"'
                r'[^>]*href=\"([^\"]+)\"',
                block, re.S | re.I)
            if not href_m:
                href_m = re.search(
                    r'href=\"([^\"]+)\"[^>]*class=\"[^\"]*stui-vodlist__thumb',
                    block, re.S | re.I)
            if not href_m:
                continue
            href = href_m.group(1).replace("&amp;", "&")

            # 归一化: 完整 URL 转相对路径
            if href.startswith(self.site_url):
                href = href[len(self.site_url):]

            if href in seen:
                continue
            seen.add(href)

            # 标题: 优先 h4.title 里的 title, 其次 h4 里的文本, 最后 thumb 的 title
            name = ""
            name_m = re.search(
                r'<h4[^>]*>[\s\S]{0,200}?title=\"([^\"]+)\"',
                block, re.S | re.I)
            if name_m:
                name = self._clean(name_m.group(1))
            if not name:
                name_m = re.search(
                    r'<h4[^>]*>[\s\S]{0,200}?<a[^>]*>([^<]+)</a>',
                    block, re.S | re.I)
                if name_m:
                    name = self._clean(name_m.group(1))
            if not name:
                # 从 thumb title
                t_m = re.search(
                    r'<a[^>]*class=\"[^\"]*stui-vodlist__thumb[^\"]*\"'
                    r'[^>]*title=\"([^\"]+)\"',
                    block, re.S | re.I)
                if t_m:
                    name = self._clean(t_m.group(1))

            # 封面
            pic = ""
            pic_m = re.search(r'data-original=\"([^\"]+)\"', block)
            if pic_m:
                pic = pic_m.group(1)
            if not pic:
                pic_m = re.search(r'src=\"([^\"]+)\"', block)
                if pic_m:
                    pic = pic_m.group(1)
            if pic and "load.gif" in pic:
                pic = ""

            # 备注: pic-text 或 detail p.text
            remarks = ""
            rem_m = re.search(
                r'class=\"[^\"]*pic-text[^\"]*\"[^>]*>([^<]+)</span>',
                block, re.I)
            if rem_m:
                remarks = self._clean(rem_m.group(1))
            if not remarks:
                rem_m = re.search(
                    r'<p\s+class=\"[^\"]*text[^\"]*\"[^>]*>([^<]*)</p>',
                    block, re.I)
                if rem_m:
                    remarks = self._clean(rem_m.group(1))

            videos.append({
                "vod_id":      href,
                "vod_name":    name or href,
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks,
            })
        return videos

    def _page_count(self, html):
        """从 HTML 中提取总页数"""
        if not html:
            return 1
        # 找 max page: href="/listnew/1-N.html" 中最大的 N
        pages = re.findall(r'/listnew/\d+-(\d+)\.html', html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        # 搜索页: 搜索页总页数通过 mac_record_total JS 变量, 但 HTML 里不一定有
        # 兜底用 999
        return 999

    # -------- 首页 --------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {"list": videos}

    # -------- 分类 --------
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        # 构造 URL: /listnew/{tid}.html  或 /listnew/{tid}-{page}.html
        # 如果有子分类筛选: /listnew/{class_id}.html (直接访问子分类)
        cls = extend.get("class", "")
        if cls:
            base_tid = cls
        else:
            base_tid = tid

        if page <= 1:
            url = "%s/listnew/%s.html" % (self.site_url, base_tid)
        else:
            url = "%s/listnew/%s-%d.html" % (self.site_url, base_tid, page)

        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  视频: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": len(videos) or 20, "total": pagecount * 20,
        }

    # -------- 搜索 --------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)

        # 搜索接口: GET /index.php/vod/search.html?wd=关键词&page=页码
        url = ("%s/index.php/vod/search.html?wd=%s&page=%d"
               % (self.site_url, keyword, page))
        self.log("search: %s" % url)
        html = self._fetch(url)

        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)

        # 总页数: 从页面分页链接提取
        pagecount = 1
        pages = re.findall(r'[?&]page=(\d+)', html)
        if pages:
            try:
                pagecount = max(int(p) for p in pages)
            except Exception:
                pass
        if pagecount <= 1:
            pagecount = 999

        return {
            "list": videos, "page": page,
            "pagecount": pagecount,
            "limit": 20, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # -------- 详情 --------
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

        # ===== 标题 =====
        # 在 stui-content__detail 里找 h1 (页面顶部也有 h1 是网站名, 要排除)
        name = ""
        detail_idx = html.find("stui-content__detail")
        if detail_idx > 0:
            detail_html = html[detail_idx:detail_idx + 2000]
            m = _RE_H1.search(detail_html)
            if m:
                name = self._clean(m.group(1))
        if not name:
            # 兜底: 用 title 标签
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                title = self._clean(m.group(1))
                # 取第一个 - 或 _ 之前的
                for sep in [" - ", "-", "_", "|"]:
                    if sep in title:
                        title = title.split(sep)[0].strip()
                        break
                name = title
        if not name:
            name = vod_id

        # ===== 封面 =====
        pic = self.default_pic
        # 优先从 stui-content__thumb 里找
        thumb_idx = html.find("stui-content__thumb")
        if thumb_idx > 0:
            thumb_html = html[thumb_idx:thumb_idx + 1500]
            m = re.search(r'data-original=\"([^\"]+)\"', thumb_html)
            if m:
                pic = self._fix_url(m.group(1))
            else:
                m = re.search(r'src=\"([^\"]+)\"', thumb_html)
                if m:
                    pic = self._fix_url(m.group(1))
        if not pic or pic == self.default_pic:
            m = re.search(
                r'<img[^>]*class=\"[^\"]*lazyload[^\"]*\"[^>]*?'
                r'data-original=\"([^\"]+)\"',
                html, re.I)
            if m:
                pic = self._fix_url(m.group(1))

        # ===== 简介 =====
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_INTRO_CONTAINER.search(html)
            if m:
                content = self._clean(m.group(1))
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # 元信息 - 从 stui-content__detail 里的 data <p> 提取
        director = ""
        actor = ""
        type_name = ""
        area = ""
        year = ""
        remarks = ""

        detail_idx = html.find("stui-content__detail")
        if detail_idx > 0:
            detail_html = html[detail_idx:detail_idx + 3000]
            # 找所有 data <p>
            for pm in re.finditer(
                    r'<p\s+class=\"[^\"]*data[^\"]*\"[^>]*>([\s\S]*?)</p>',
                    detail_html, re.S | re.I):
                p_text = self._clean(pm.group(1))
                if not p_text:
                    continue
                if "导演" in p_text and "：" in p_text:
                    director = p_text.split("：", 1)[1].strip()
                elif "主演" in p_text and "：" in p_text:
                    actor = p_text.split("：", 1)[1].strip()
                elif "类型" in p_text and "：" in p_text:
                    type_name = p_text.split("：", 1)[1].strip()
                elif "地区" in p_text and "：" in p_text:
                    area = p_text.split("：", 1)[1].strip()
                elif "年份" in p_text and "：" in p_text:
                    year = p_text.split("：", 1)[1].strip()
                elif "更新" in p_text and "：" in p_text:
                    remarks = p_text.split("：", 1)[1].strip()

        # 评分
        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)
        else:
            m = _RE_SCORE_NUM.search(html)
            if m:
                score = m.group(1)

        # ===== 剧集提取 =====
        # 结构: 线路头 = stui-pannel__head (含 h3.title = 线路名)
        #       线路列表 = stui-content__playlist (紧跟在头之后的 pannel_bd 里)
        # 先取所有 head 的位置和线路名, 再取所有 playlist 位置和内容, 按位置顺序配对

        # 提取线路名: 从 stui-pannel__head 里找 h3.title 或直接文本
        line_heads = []  # (pos, name)
        for m in re.finditer(
                r'stui-pannel__head[^>]*>([\s\S]{0,400}?)(?:</h\d>|</div>)',
                html, re.S | re.I):
            # 提取 h3.title 里的文字, 没有则提取所有非标签文字
            head_html = m.group(1)
            txt = ""
            hm = re.search(
                r'<h\d[^>]*title[^>]*>([\s\S]*?)</h\d>',
                head_html, re.I)
            if hm:
                txt = self._clean(hm.group(1))
            if not txt:
                txt = self._clean(head_html)
            if not txt or len(txt) > 50:
                continue
            # 过滤掉非线路的 head
            if any(kw in txt for kw in [
                "剧情介绍", "猜你喜欢", "影片评论", "热播榜", "本周热门",
                "相关推荐", "最新", "排行榜", "评论", "点赞", "收藏"]):
                continue
            line_heads.append((m.start(), txt))

        # 找所有 playlist ul
        playlists = []  # (pos, html)
        for m in _RE_PLAYLIST.finditer(html):
            playlists.append((m.start(), m.group(1)))

        self.log("  线路头: %d, playlist: %d" % (len(line_heads), len(playlists)))

        # 配对: 第 N 个 head 对应第 N 个 playlist
        groups = {}
        for i, (pos, ep_html) in enumerate(playlists):
            if i < len(line_heads):
                origin_name = line_heads[i][1]
            else:
                origin_name = "线路%d" % (i + 1)

            eps = []
            for em in _RE_EPISODE.finditer(ep_html):
                ep_href = em.group(1).replace("&amp;", "&")
                ep_name = self._clean(em.group(2))
                if ep_href and ep_name:
                    eps.append((ep_name, ep_href))

            if eps:
                groups[origin_name] = eps

        self.log("  剧集组: %s" % {k: len(v) for k, v in groups.items()})

        if not groups:
            return {"list": []}

        # 组装
        play_from = list(groups.keys())
        play_url = []
        for origin in play_from:
            eps = groups[origin]
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        # 备注信息
        remarks_parts = []
        if remarks:
            remarks_parts.append(remarks)
        if type_name:
            remarks_parts.append(type_name)
        if area:
            remarks_parts.append(area)
        if year:
            remarks_parts.append(year)
        if not remarks_parts:
            remarks_parts.append("%d条线路" % len(groups))
        remarks_str = " / ".join(remarks_parts)

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remarks_str,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # -------- 播放 --------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

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

        # 解析 player_aaaa
        obj = _parse_player_json(html)
        real_url = ""
        if obj:
            url_enc = obj.get("url", "")
            if url_enc:
                # 部分站是 URL 编码, 部分是普通字符串
                try:
                    decoded = urllib.parse.unquote(url_enc)
                    if decoded.startswith("http"):
                        real_url = decoded
                except Exception:
                    pass
                if not real_url and url_enc.startswith("http"):
                    real_url = url_enc

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

        # 兜底: 交给 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res
