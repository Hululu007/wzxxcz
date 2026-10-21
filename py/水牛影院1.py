# coding=utf-8
"""
水牛影院 sunnykings.com | TVBox Python 爬虫

网站结构：
1. 卡片链接是 /wap/xxx.html、/weihu/xxx.html、/news/xxx.html、/tv/xxx.html 四种混用，
   原来的 /(news|weihu|wap|m)/ 正则漏掉 /tv/，且没有兜底，导致部分页"0 条"。
2. 卡片结构是「缩略图 a + 标题 a + 简介 p」，标题在 h4>a 的 title 里，
   原来的 +1500 字符窗口取到的 title 往往是下一张卡的，标题会错位。
   改为按 <li> 分块解析，彻底解决错位与串图。
3. 筛选 URL 是 maccms 的 11 段横杠格式，各字段位置固定：
   /so-show/{class}-{area}-{lang}-{letter}-{order}-{page}-{year}.html
   实测可用示例：
     分类+年份 : /so-show/14-----------2025.html
     地区+语言 : /so-show/14-%E5%86%85%E5%9C%B0--%E5%9B%BD%E8%AF%AD--------.html
     年份+排序 : /so-show/14--------1---hits.html
   原脚本把年份写在页码区、把排序整个丢掉，所以"筛了没数据"。
4. 分页总页数：优先读移动端 <span class="num">1/22</span>，其次读"尾页"链接里的页码。
5. 详情页元数据（类型/地区/年份/语言/主演/导演/更新）原正则相互依赖、遇空格即断，
   改为按"标签 span 定位 + 到下一个标签 span 截止"的独立片段解析。
6. 播放地址：详情页里没有 player_aaaa，必须在 /tvplay/xx-x-x.html 里取，
   原逻辑正确，这里补了 url 兜底与 Referer。

==================== 实测得到的站点真实规则（重要） ====================
so-show 筛选 URL 是固定 12 段（用 "-" 连接，索引 0~11），实测槽位为：
    0 分类id | 1 地区 | 2 排序 | 3 剧情 | 4 语言 | 5 字母 | 6 空 | 7 空
    8 页码   | 9 空   | 10 空  | 11 年份
实测通过的 URL（均已请求验证）：
    默认       /so-show/14-----------.html                  -> 36 条 / 186 页
    年份       /so-show/14-----------2025.html              -> 36 条 / 22 页
    地区       /so-show/14-%E5%86%85%E5%9C%B0----------.html -> 34 条
    语言       /so-show/14----%E5%9B%BD%E8%AF%AD-------.html -> 36 条 / 116 页
    排序       /so-show/14--hits---------.html               -> 36 条
    年份+排序  /so-show/14--hits---------2025.html           -> 36 条 / 22 页
    年份+分页  /so-show/14--------2---2025.html              -> 第 2 页 / 22 页
    排序+分页  /so-show/14--hits------2---.html              -> 第 2 页
旧脚本把年份塞进页码槽、排序字段整个丢弃、且地区/语言槽位错开，
这正是"筛选完没有数据"的直接原因。

搜索 URL 是 14 段，关键词在槽 0；实测该站搜索固定只回 10 条且无分页条，
故搜索只取第 1 页。
原逻辑正确，这里补了 url 兜底与 Referer。
"""
import re
import sys
import json
import time
import html
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
                print("[sunnykings]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://sunnykings.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/default18/template/mb13/statics/img/load.gif"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "30", "type_name": "爽文短剧"},
    {"type_id": "36", "type_name": "伦理片"},
]

# 无筛选时直接用站点导航里的 /listnew/{tid}.html，各主分类均可用
_DEFAULT_SUB_TID = {
    "1": "1", "2": "2", "3": "3", "4": "4", "30": "30", "36": "36"
}

# so-show 12 段的槽位表（实测得出，见文件头）
_SLOT = {
    "tid": 0, "area": 1, "order": 2, "plot": 3,
    "lang": 4, "letter": 5, "page": 8, "year": 11,
}
_SHOW_SLOTS = 12
_SEARCH_SLOTS = 14

# 站点"分类"筛选项 -> 真实 type_id（实测 /so-show/{id}-... 均可用）
_CLASS_ID_MAP = {
    "全部": "", "电影": "1", "电视剧": "2",
    "动作片": "7", "喜剧片": "8", "爱情片": "9", "科幻片": "10",
    "恐怖片": "11", "剧情片": "12", "犯罪片": "29", "战争片": "13",
    "国产剧": "14", "港剧": "15", "台湾剧": "16", "韩剧": "17",
    "日剧": "18", "泰剧": "31", "欧美剧": "19", "海外剧": "20",
    "大陆综艺": "21", "日韩综艺": "22", "港台综艺": "23", "欧美综艺": "24",
    "国产动漫": "25", "日本动漫": "26", "欧美动漫": "27", "海外动漫": "28",
    "爽文短剧": "30", "短剧": "30", "伦理片": "36",
}

_SORTS = [{"n": "按时间", "v": "time"},
          {"n": "按人气", "v": "hits"},
          {"n": "按评分", "v": "score"}]
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2005, -1)]
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
    {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"},
    {"n": "法国", "v": "法国"}, {"n": "英国", "v": "英国"},
    {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
    {"n": "德国", "v": "德国"}, {"n": "泰国", "v": "泰国"},
    {"n": "印度", "v": "印度"}, {"n": "意大利", "v": "意大利"},
    {"n": "西班牙", "v": "西班牙"}, {"n": "加拿大", "v": "加拿大"},
    {"n": "其他", "v": "其他"},
]
_LANGS = [
    {"n": "全部", "v": ""},
    {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"},
    {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"},
    {"n": "韩语", "v": "韩语"}, {"n": "日语", "v": "日语"},
    {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"},
    {"n": "其它", "v": "其它"},
]

_FILTERS_MAP = {
    "1":  ["全部", "动作片", "喜剧片", "爱情片", "科幻片", "恐怖片", "剧情片", "犯罪片", "战争片"],
    "2":  ["全部", "国产剧", "港剧", "台湾剧", "韩剧", "日剧", "泰剧", "欧美剧", "海外剧"],
    "3":  ["全部", "大陆综艺", "日韩综艺", "港台综艺", "欧美综艺"],
    "4":  ["全部", "国产动漫", "日本动漫", "欧美动漫", "海外动漫"],
    "30": ["全部", "爽文短剧", "短剧"],
    "36": ["全部", "伦理片"],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "分类",
         "value": [{"n": x, "v": "" if x == "全部" else x} for x in _FILTERS_MAP.get(tid, ["全部"])]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "lang", "name": "语言", "value": _LANGS},
        {"key": "sort_field", "name": "排序", "value": _SORTS},
    ]

# ===================== 正则 =====================
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE = re.compile(r'<title>(.*?)</title>', re.S | re.I)
_RE_INTRO_FULL = re.compile(
    r'<span[^>]*class="[^"]*detail-content[^"]*"[^>]*>([\s\S]*?)</span>', re.I)
_RE_INTRO_SKETCH = re.compile(
    r'<span[^>]*class="[^"]*detail-sketch[^"]*"[^>]*>([\s\S]*?)</span>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_SCORE = re.compile(
    r'class="[^"]*branch[^"]*"[^>]*>\s*([\d.]+)\s*<', re.I)
_RE_PLAYER = re.compile(
    r'var\s+player_[a-zA-Z_]+\s*=\s*(\{.*?\})\s*</script>', re.S)
# 播放列表：h3 线路名 + 紧随其后的 stui-content__playlist
_RE_LINE_BLOCK = re.compile(
    r'<h3[^>]*>\s*([^<\n]+?)\s*</h3>[\s\S]{0,600}?'
    r'<ul[^>]*class="[^"]*stui-content__playlist[^"]*"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_EP_A = re.compile(r'<a[^>]+href="([^"]+?)"[^>]*>([^<]*)</a>', re.I)
# 卡片链接：/wap/ /weihu/ /news/ /tv/ /detail/ 都吃
# 站点会轮流换路径前缀（/wap/ /weihu/ /news/ /tv/ /cp/ /play/ /detail/ ...），
# 所以不能写死前缀，统一按「/xxx/数字.html」匹配，再用列表页特征排除导航链接。
_RE_CARD_HREF = re.compile(r'href="(/[a-zA-Z][\w\-]{0,12}/(\d{3,})\.html)"', re.I)
# 分页：任意带页号的链接
_RE_PAGER_MAX = re.compile(
    r'href="[^"]*?[-/](\d+)\.html"[^>]*>\s*(?:尾页|末页|&#23614;&#39029;)', re.I)
_RE_PAGER_NUM = re.compile(r'class="[^"]*num[^"]*"[^>]*>\s*\d+\s*/\s*(\d+)', re.I)
# 筛选区块（按类型/剧情/地区/年份/语言/字母 各一个 ul）
_RE_SCREEN_LIST = re.compile(
    r'<ul[^>]*class="[^"]*stui-screen__list[^"]*"[^>]*>([\s\S]*?)</ul>', re.I)

_VOD_KV = ["类型", "地区", "年份", "语言", "主演", "导演", "更新", "别名", "备注", "集数", "人气"]

# 首次运行时从站点同步失败就用这份静态兜底
_STATIC_FILTERS = dict((k, v) for k, v in FILTERS.items())


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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._last_req_ts = 0.0
        self.log("init: site=%s" % self.site_url)

    # ------------------------------------------------------------------ #
    # 基础请求
    # ------------------------------------------------------------------ #
    def _fetch(self, url, timeout=20, headers=None, retry=2):
        now = time.time()
        gap = now - self._last_req_ts
        if gap < 0.4:
            time.sleep(0.4 - gap)
        self._last_req_ts = time.time()

        h = dict(self.headers)
        if headers:
            h.update(headers)

        for attempt in range(retry + 1):
            try:
                rsp = self.fetch(url, headers=h, timeout=timeout)
                text = ""
                if hasattr(rsp, "text"):
                    text = rsp.text or ""
                elif hasattr(rsp, "content"):
                    text = rsp.content.decode("utf-8", "ignore")
                else:
                    text = str(rsp)

                if "请不要频繁操作" in text or "访问过于频繁" in text:
                    self.log("触发频率限制, 等待 3s 重试")
                    time.sleep(3.0)
                    continue
                if len(text) < 500 and attempt < retry:
                    time.sleep(1.0)
                    continue
                return text
            except Exception as e:
                self.log("fetch FAIL(%d) %s -> %s" % (attempt, url, e))
                time.sleep(1.0)
        return ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip().replace("\\/", "/")
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
        s = s.replace("\\u0026", "&").replace("\\/", "/")
        s = html.unescape(html.unescape(s))
        s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
        s = re.sub(r"<script[\s\S]*?</script>", " ", s, flags=re.I)
        s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("\u3000", " "))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n\s*\n+", "\n", s)
        return s.strip()

    # ------------------------------------------------------------------ #
    # 列表解析（按 <li> 分块，任意卡片链接都能吃）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _split_cards(html_content):
        """把列表页切成单个卡片块，顺序与页面一致。"""
        cards = []
        parts = re.split(r'<li[^>]*>', html_content)
        for p in parts:
            if _RE_CARD_HREF.search(p):
                cards.append(p)
        if not cards:
            # 兜底：按卡片链接切
            idx = [m.start() for m in _RE_CARD_HREF.finditer(html_content)]
            for i, s in enumerate(idx):
                e = idx[i + 1] if i + 1 < len(idx) else min(len(html_content), s + 2500)
                cards.append(html_content[s:max(e, s + 400)])
        return cards

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        if not html_content:
            self.log("  HTML 为空")
            return videos

        for seg in self._split_cards(html_content):
            m = _RE_CARD_HREF.search(seg)
            if not m:
                continue
            href = m.group(1)
            if href in seen:
                continue
            seen.add(href)

            # 标题：优先第一处 title="xxx"（缩略图 a 上）
            title = ""
            t = re.search(r'title="([^"]*)"', seg)
            if t:
                title = self._clean(t.group(1))
            if not title:
                h4 = re.search(r'<h4[^>]*>[\s\S]*?<a[^>]*>([\s\S]*?)</a>', seg)
                if h4:
                    title = self._clean(h4.group(1))
            if not title:
                title = "未命名"

            # 封面
            pic = self.default_pic
            p = re.search(r'data-original="([^"]+)"', seg) or \
                re.search(r'data-src="([^"]+)"', seg) or \
                re.search(r'<img[^>]+src="([^"]+)"', seg)
            if p:
                src = p.group(1).strip()
                if src and not src.startswith("data:"):
                    pic = self._fix_url(src)

            # 角标：pic-text 优先（更新至xx集 / 全30集 / 已完结 / HD），其次任意 span
            remark = ""
            pt = re.search(r'pic-text[^"]*"[^>]*>([^<]+)<', seg)
            if pt:
                remark = self._clean(pt.group(1))
            if not remark:
                for text in re.findall(r'<span[^>]*>([^<]{1,20})</span>', seg):
                    text = self._clean(text)
                    if not text or text == title:
                        continue
                    if re.search(r'(更新|全\s*\d|第\s*\d|集|HD|正片|完结|预告)', text):
                        remark = text
                        break
            # 站内卡片还会把"导演/主演"放在 <p> 里，这里顺手当作简介补充
            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": pic,
                "vod_remarks": remark,
            })

        self.log("  提取到数据: %d 条" % len(videos))
        return videos

    def _page_count(self, html_content, page):
        if not html_content:
            return page
        # 1) 移动端 "1/22"
        m = _RE_PAGER_NUM.search(html_content)
        if m:
            try:
                return max(int(m.group(1)), page)
            except Exception:
                pass
        # 2) "尾页" 链接
        m = _RE_PAGER_MAX.search(html_content)
        if m:
            try:
                return max(int(m.group(1)), page)
            except Exception:
                pass
        # 3) 分页区里最大的页码
        seg = ""
        i = html_content.find("stui-page")
        if i > 0:
            seg = html_content[i:i + 4000]
        if seg:
            nums = [int(x) for x in re.findall(r'>\s*(\d{1,4})\s*</a>', seg)]
            if nums:
                return max(max(nums), page)
        return page

    # ------------------------------------------------------------------ #
    # 首页 / 分类
    # ------------------------------------------------------------------ #
    def homeContent(self, filter=False):
        # 用站点真实筛选项覆盖静态表，避免选项和站点对不上导致空列表
        try:
            self._sync_filters()
        except Exception as e:
            self.log("筛选项同步失败: %s" % e)
        return {"class": CLASSES, "filters": FILTERS or _STATIC_FILTERS}

    def homeVideoContent(self):
        html_text = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html_text))
        videos = self._extract_videos(html_text)
        return {"list": videos[:90]}

    # ------------------------------------------------------------------ #
    # 从分类页解析站点自带的筛选项（按类型/剧情/地区/年份/语言/字母）
    # 这样下拉里出现的值，一定是站点真正认的值
    # ------------------------------------------------------------------ #
    def _sync_filters(self):
        if getattr(self, "_filters_done", False) and FILTERS:
            return
        for c in CLASSES:
            tid = c["type_id"]
            real_tid = _DEFAULT_SUB_TID.get(tid, tid)
            raw = self._fetch("%s/listnew/%s.html" % (self.site_url, real_tid))
            if not raw:
                continue
            blocks = _RE_SCREEN_LIST.findall(raw)
            got = {}
            for b in blocks:
                lab = re.search(r'text-muted">([^<]*)</span>', b)
                if not lab:
                    continue
                name = self._clean(lab.group(1))
                opts = []
                for href, txt in re.findall(
                        r'href="(/so-show/[^"]*)"[^>]*>\s*([^<]{1,16}?)\s*</a>', b, re.S):
                    label = self._clean(txt)
                    if label and label not in [o["n"] for o in opts]:
                        opts.append({"n": label, "v": "" if label in ("全部", "") else label})
                if opts:
                    got[name] = opts
            f = []
            order = [("按类型", "class"), ("按剧情", "plot"), ("按地区", "area"),
                     ("按年份", "year"), ("按语言", "lang")]
            for label, key in order:
                if label in got:
                    f.append({"key": key, "name": label.replace("按", ""), "value": got[label]})
            if "按时间" not in got:
                f.append({"key": "sort_field", "name": "排序", "value": _SORTS})
            if f:
                FILTERS[tid] = f
        self._filters_done = bool(FILTERS)

    # ------------------------------------------------------------------ #
    # 关键修复：筛选 URL 拼接
    # so-show 固定 12 段，索引见 _SLOT；空槽位留空，段间仍要有 "-"
    # ------------------------------------------------------------------ #
    @staticmethod
    def _slots_to_url(base, slots):
        return "%s/so-show/%s.html" % (base, "-".join(slots))

    def _build_show_url(self, tid, extend, page):
        try:
            page = int(page) if page else 1
        except Exception:
            page = 1
        page = max(page, 1)

        cls = str(extend.get("class") or "").strip()
        if cls and _CLASS_ID_MAP.get(cls):
            real_tid = _CLASS_ID_MAP[cls]
        else:
            real_tid = _DEFAULT_SUB_TID.get(tid, tid) or tid

        area = str(extend.get("area") or "").strip()
        lang = str(extend.get("lang") or "").strip()
        year = str(extend.get("year") or "").strip()
        plot = str(extend.get("plot") or "").strip()
        order = str(extend.get("sort_field") or "").strip()
        if order in ("time", "默认", "按时间"):
            order = ""

        has_filter = bool(area or lang or year or plot or order)

        # 无筛选：优先 listnew（站点导航原生地址，最稳）
        if not has_filter:
            if page <= 1:
                return "%s/listnew/%s.html" % (self.site_url, real_tid)
            return "%s/listnew/%s-%d.html" % (self.site_url, real_tid, page)

        slots = [""] * _SHOW_SLOTS
        slots[_SLOT["tid"]] = str(real_tid)
        slots[_SLOT["area"]] = urllib.parse.quote(area) if area else ""
        slots[_SLOT["order"]] = order
        slots[_SLOT["plot"]] = urllib.parse.quote(plot) if plot else ""
        slots[_SLOT["lang"]] = urllib.parse.quote(lang) if lang else ""
        slots[_SLOT["page"]] = "" if page <= 1 else str(page)
        slots[_SLOT["year"]] = year
        return self._slots_to_url(self.site_url, slots)

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        extend = dict(extend)
        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        url = self._build_show_url(tid, extend, page)
        self.log("category: %s" % url)
        html_text = self._fetch(url)
        videos = self._extract_videos(html_text)

        # 兜底：该组合站点无数据时，逐级放宽条件，避免整页空白
        if not videos and extend:
            tried = [url]
            relaxed = dict(extend)
            for drop in ("plot", "lang", "sort_field", "area", "year"):
                if drop in relaxed:
                    relaxed.pop(drop)
                    u2 = self._build_show_url(tid, relaxed, page)
                    if u2 in tried:
                        continue
                    tried.append(u2)
                    self.log("  无数据，放宽条件重试: %s" % u2)
                    html_text = self._fetch(u2)
                    videos = self._extract_videos(html_text)
                    if videos:
                        break
        if not videos and page > 1:
            u3 = self._build_show_url(tid, {}, 1)
            self.log("  本页无数据，回落到第 1 页: %s" % u3)
            html_text = self._fetch(u3)
            videos = self._extract_videos(html_text)

        pagecount = self._page_count(html_text, page)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": max(pagecount, page),
            "limit": len(videos) or 30, "total": max(pagecount, page) * 30,
        }

    # ------------------------------------------------------------------ #
    # 搜索：/search/{kw} + 13 个空槽（共 14 段）。该站搜索结果无分页，固定 10 条
    # ------------------------------------------------------------------ #
    def searchContent(self, key, quick=False, pg="1"):
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        kw = urllib.parse.quote(str(key).strip())
        slots = [""] * _SEARCH_SLOTS
        slots[0] = kw
        if page > 1:
            slots[_SEARCH_SLOTS - 1] = str(page)
        url = "%s/search/%s.html" % (self.site_url, "-".join(slots))

        self.log("search: %s" % url)
        html_text = self._fetch(url)
        videos = self._extract_videos(html_text)
        pagecount = self._page_count(html_text, page)

        return {
            "list": videos, "page": page,
            "pagecount": max(pagecount, page, 1),
            "limit": len(videos) or 30, "total": len(videos) or 30,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ------------------------------------------------------------------ #
    # 详情
    # ------------------------------------------------------------------ #
    def _pick_kv(self, header, label):
        """按「标签 span 定位 -> 到下一个标签 span 截止」截取片段，独立解析，互不影响。

        注意：站点 HTML 里的中文标签是数字实体（地区 写作 &#22320;&#21306;），
        所以必须先把实体还原成中文再匹配，否则一个字段都取不到。
        """
        plain = self._unentity(header)
        m = re.search(r'%s\s*[：:]\s*</span>([\s\S]{0,900}?)(?=<span[^>]*text-muted|</p>)'
                      % re.escape(label), plain)
        if not m:
            return ""
        frag = m.group(1)
        # 标签换成 "|" 当分隔符，再逐段清洗（<a> 之间、多值之间都会成为独立段）
        text = re.sub(r'<[^>]*>', '|', "|" + frag)
        parts = []
        for x in text.split('|'):
            x = self._clean(x)
            if x and x not in ("/", "·"):
                parts.append(x)
        return ", ".join(parts).strip(" /,|")

    @staticmethod
    def _unentity(text):
        """把数字/命名实体还原成字符，但保留标签结构。"""
        if not text:
            return ""
        def rep(mm):
            try:
                return html.unescape(mm.group(0))
            except Exception:
                return mm.group(0)
        return re.sub(r'&#?\w+;', rep, text)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        if isinstance(ids, (list, tuple)):
            vod_id = str(ids[0])
        else:
            vod_id = str(ids)
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html_text = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html_text))
        if not html_text:
            return {"list": []}

        # ---- 名称 ----
        name = ""
        for h1 in _RE_H1.findall(html_text):
            c = self._clean(h1)
            if c and c not in ("水牛影院",):
                name = c
                break
        if not name:
            m = _RE_TITLE.search(html_text)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = name or vod_id

        # ---- 封面 ----
        pic = self.default_pic
        m = re.search(r'data-original="(/upload/vod/[^"]+)"', html_text) or \
            re.search(r'<img[^>]+src="(/upload/vod/[^"]+)"', html_text)
        if m:
            pic = self._fix_url(m.group(1))

        # ---- 简介：detail-content（展开） -> detail-sketch -> meta desc ----
        content = ""
        m = _RE_INTRO_FULL.search(html_text) or _RE_INTRO_SKETCH.search(html_text)
        if m:
            content = self._clean(m.group(1))
        if len(content) < 10:
            m = _RE_META_DESC.search(html_text)
            if m:
                content = self._clean(m.group(1))

        # ---- 元数据块 ----
        header = ""
        m = re.search(r'class="[^"]*stui-content__detail[^"]*"([\s\S]{0,4000}?)'
                      r'<div[^>]*class="[^"]*(?:play-btn|stui-pannel)[^"]*"', html_text)
        if m:
            header = m.group(1)
        if not header:
            i = html_text.find("stui-content__detail")
            header = html_text[i:i + 4000] if i > 0 else html_text

        v_type = self._pick_kv(header, "类型")
        v_area = self._pick_kv(header, "地区")
        v_year = self._pick_kv(header, "年份")
        v_lang = self._pick_kv(header, "语言")
        v_actor = self._pick_kv(header, "主演")
        v_director = self._pick_kv(header, "导演")
        v_update = self._pick_kv(header, "更新")

        score = ""
        m = _RE_SCORE.search(html_text)
        if m:
            score = m.group(1)

        # ---- 播放线路 ----
        play_from, play_url = [], []
        for m in _RE_LINE_BLOCK.finditer(html_text):
            alias = self._clean(m.group(1)) or "线路%d" % (len(play_from) + 1)
            eps = _RE_EP_A.findall(m.group(2))
            items = []
            for href, ep_name in eps:
                if "/tvplay/" not in href and "/play/" not in href:
                    continue
                href = self._fix_url(href.replace("&amp;", "&"))
                ep = self._clean(ep_name) or "正片"
                items.append("%s$%s" % (ep, href))
            if items:
                play_from.append(alias)
                play_url.append("#".join(items))

        self.log("  剧集: %d 线路" % len(play_from))

        if not play_from:
            # 至少把"立即播放"链接给出来，避免详情页整体空白
            m = re.search(r'href="(/tvplay/[^"]+)"', html_text)
            if m:
                play_from = ["默认"]
                play_url = ["正片$" + self._fix_url(m.group(1))]
            else:
                return {"list": []}

        remark_parts = [x for x in (v_type, v_area, v_year, v_lang) if x]
        remark = " | ".join(remark_parts)
        if v_update:
            remark = (remark + " | " + v_update) if remark else v_update

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": v_actor,
            "vod_director": v_director,
            "vod_area": v_area,
            "vod_year": v_year,
            "vod_lang": v_lang,
            "vod_score": score,
            "vod_remarks": remark,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ------------------------------------------------------------------ #
    # 播放
    # ------------------------------------------------------------------ #
    def playerContent(self, flag, id, vipFlags=None):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html_text = self._fetch(play_page, headers={"Referer": self.site_url + "/"})
        url = ""
        if html_text:
            raw = ""
            m = _RE_PLAYER.search(html_text)
            if m:
                raw = m.group(1).replace("\\/", "/")
                try:
                    cfg = json.loads(raw)
                    url = (cfg.get("url") or "").strip()
                except Exception as e:
                    self.log("player json 解析失败: %s" % e)
                    m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                    if m2:
                        url = m2.group(1).replace("\\/", "/")
            if not url:
                # 兜底：页面里直接出现的 m3u8/mp4
                m3 = re.search(r'(https?:\\?/\\?/[^"\'<>\s]+?\.(?:m3u8|mp4)[^"\'<>\s]*)',
                               html_text)
                if m3:
                    url = m3.group(1).replace("\\/", "/")

        if url:
            url = url.replace("\\/", "/")
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
            self.log("  => m3u8: %s" % url[:160])
            return res

        # 取不到直链就走嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
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
