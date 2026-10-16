# coding=utf-8
"""
影视大全 iysdq1.com | TVBox Python 爬虫

严格依据网页真实源码写：

  1. 播放页源码里 var player_aaaa = {...}
     - "url" 是"入口地址"（各条线路自己的 m3u8 域名）
     - "from" 是线路 id（如 dyttm3u8 / xiguam3u8）
     - "link_next" 是下一集的播放页路径

  2. player.js -> MacPlayer.Init() -> MacPlayer.Play()
     document.write('<script src="/static/player/<from>.js">')
     然后由 /static/player/<from>.js 生成 iframe。

  3. <from>.js 里的真实源码（你贴的）：
       MacPlayer.Html = '<iframe border="0" src="https://p.iysdq.com/player/?url='
           + MacPlayer.PlayUrl
           + '&next=' + (window.location.protocol + '//' + window.location.host + MacPlayer.PlayLinkNext)
           + '&tittle=' + document.title.split("-")[0]
           + '" ...></iframe>';
       MacPlayer.Show();
     所以真正加载的页面是：
       https://p.iysdq.com/player/?url=<player_aaaa.url>&next=<宿主+link_next>&tittle=<标题>

  4. player 页返回的 HTML 里 config 是这样：
       var config = {
           "api": "/dmku/",
           "url": "cmtYPPmuW+sEJGAi8UkSOgkcAgG9yC4/XZzqaldDzJZwHS8gxuOezNMuxKJnKUVVWCTXR0H+pq3fIJTPeRyLRBmS+J+yFUDwE34=",
           "id":"b6ef8037ca943f4b1d60",
           ...
       }
     其中 config.url 是 Base64 密文，不是明文 m3u8。

  5. player 页里的 YKQ.start() 里这一行才是真正播放：
       YKQ.play(rc4(config.url, '202306051426239465', 1));
     rc4 函数的实现（定义在 YKQ 源码最末）：
       - t == 1 时：data = atob(data)  （即先 Base64 解码）
       - 标准 RC4 解密（密钥 '202306051426239465'）
       - 返回 decodeURIComponent(cipher)

  6. 所以 Python 端要做的、也是唯一正确的做法：
       a) 从播放页拿 player_aaaa.url、player_aaaa.link_next
       b) 照 MacPlayer.Html 拼接：
            https://p.iysdq.com/player/?url=<url>&next=<宿主+link_next>&tittle=<标题>
       c) 请求这个 player 页
       d) 从返回 HTML 里正则抓出 config 的 "url":"..."
       e) 对抓到的密文执行 atob → RC4(key='202306051426239465') → urldecode
       f) 得到的才是真实 m3u8 地址，返回给播放器

  7. 返回 header：照 m3u8 真实请求（F12 cURL）只有真实 UA，无 Referer、无 Origin。
"""
import re
import sys
import json
import base64
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

# 播放器真实 UA（从 F12 抓 m3u8 请求的 cURL 抄来）
PLAYER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36 Edg/155.0.0.0")

# ★ player 页的真正入口（来自 <from>.js 里 MacPlayer.Html 的 src）
PLAYER_BASE = "https://p.iysdq.com/player/"

# RC4 密钥（来自 YKQ 源码：YKQ.play(rc4(config.url,'202306051426239465',1)))
RC4_KEY = "202306051426239465"

DEFAULT_PIC = HOST + "/template/shoutu45/assets/images/img-bj-k.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "5", "type_name": "短剧"},
]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
    {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"},
    {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
    {"n": "英国", "v": "英国"}, {"n": "法国", "v": "法国"},
    {"n": "德国", "v": "德国"}, {"n": "意大利", "v": "意大利"},
    {"n": "西班牙", "v": "西班牙"}, {"n": "俄罗斯", "v": "俄罗斯"},
    {"n": "加拿大", "v": "加拿大"}, {"n": "印度", "v": "印度"},
    {"n": "泰国", "v": "泰国"}, {"n": "其它", "v": "其它"},
]

_SORTS = [
    {"n": "最新", "v": ""},
    {"n": "最热", "v": "hits"},
    {"n": "评分", "v": "score"},
]

_FILTERS_MAP = {
    "1": ["全部", "动作片", "喜剧片", "科幻片", "恐怖片", "爱情片", "剧情片",
          "战争片", "记录片", "动画片", "惊悚", "犯罪", "悬疑", "冒险", "奇幻",
          "家庭", "历史", "传记", "古装", "音乐", "同性", "运动", "武侠",
          "短片", "歌舞", "西部", "儿童", "灾难", "戏曲", "真人秀", "青春"],
    "2": ["全部", "国产剧", "欧美剧", "香港剧", "韩国剧", "台湾剧", "日本剧",
          "海外剧", "泰国剧", "剧情", "爱情", "喜剧", "悬疑", "犯罪", "古装",
          "动作", "奇幻", "惊悚", "家庭", "历史", "科幻", "战争", "同性",
          "武侠", "冒险", "恐怖", "纪录", "传记", "短片", "运动", "音乐",
          "儿童", "歌舞", "西部", "灾难"],
    "3": ["全部", "真人秀", "脱口秀", "国产综艺", "喜剧", "晚会", "综艺",
          "音乐", "纪录", "游戏", "生活", "港台综艺", "日韩综艺", "剧情",
          "文化", "相声", "情感", "悬疑", "欧美综艺", "美食", "竞技"],
    "4": ["全部", "动画", "冒险", "喜剧", "奇幻", "剧情", "科幻", "动作",
          "儿童", "悬疑", "都市", "家庭", "国漫", "日常", "爱情", "玄幻",
          "日漫", "音乐", "治愈", "短片", "古风", "犯罪", "武侠", "运动",
          "校园"],
    "5": ["全部", "AI漫剧", "短剧", "剧情", "爱情", "爽文", "古装", "短片",
          "悬疑", "喜剧", "奇幻", "都市", "玄幻", "犯罪", "家庭", "穿越",
          "惊悚", "武侠", "科幻", "动作", "冒险", "恐怖", "青春", "历史"],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "分类",
         "value": [{"n": x, "v": "" if x == "全部" else x}
                   for x in _FILTERS_MAP.get(tid, ["全部"])]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]


# ===================== 正则 =====================
_RE_CARD = re.compile(
    r'<a[^>]*class="public-list-exp"[^>]*href="(/voddetail/\d+\.html)"[^>]*title="([^"]*)"'
    r'[\s\S]{0,400}?<img[^>]*?data-src="([^"]*)"'
    r'[\s\S]{0,400}?<span class="public-list-prb[^"]*">([^<]*)</span>',
    re.S | re.I)

_RE_TITLE = re.compile(r'<div class="this-desc-title">([^<]*)</div>', re.I)
_RE_PIC_BJ = re.compile(
    r'<div class="this-pic-bj"\s+style="background-image:\s*url\(\'([^\']+)\'\)', re.I)
_RE_INTRO = re.compile(
    r'<div id="height_limit"[^>]*>\s*<strong[^>]*>描述:</strong>([\s\S]*?)</div>',
    re.S | re.I)
_RE_SCORE = re.compile(r'<div class="fraction">([\d.]+)</div>', re.I)
_RE_DIRECTOR = re.compile(
    r'<div class="this-info"><strong class="r6">导演:</strong>([\s\S]*?)</div>', re.I)
_RE_ACTOR = re.compile(
    r'<div class="this-info"><strong class="r6">演员:</strong>([\s\S]*?)</div>', re.I)
_RE_INFO = re.compile(
    r'<div class="this-desc-info">([\s\S]*?)</div>\s*<div class="this-desc-tags"', re.I)
_RE_A_TAG = re.compile(r'<a[^>]*>([^<]+)</a>', re.I)

_RE_LINE_TAB = re.compile(
    r'<a\s+data-form="([^"]+)"[^>]*class="vod-playerUrl[^"]*"[^>]*>'
    r'[\s\S]*?&nbsp;([^<]+)<span class="badge">(\d+)</span>',
    re.S | re.I)

_RE_ANTHOLOGY_BOX = re.compile(
    r'<div class=[\'"]anthology-list-box[^\'"]*[\'"]>([\s\S]*?)</ul></div></div>',
    re.S | re.I)
_RE_EPISODE = re.compile(
    r'<a class="hide"[^>]*href="(/vodplay/\d+-\d+-\d+\.html)"[^>]*>\s*<span>([^<]+)</span>',
    re.S | re.I)

_RE_PAGE_INFO = re.compile(r'<div class="rg10">\s*(\d+)\s*&nbsp;/\s*&nbsp;(\d+)\s*页', re.I)
_RE_TOTAL = re.compile(r"\$\('\.hl-total'\)\.html\('(\d+)'\)", re.I)

# 播放页源码里的 player_aaaa：var player_aaaa={...}</script>
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)

# player 页返回的 HTML 里的 config.url（加密串，纯 Base64 字符）
_RE_CONFIG_URL = re.compile(r'"url"\s*:\s*"([A-Za-z0-9+/=]+)"', re.I)


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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=15, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            return self.fetch(url, headers=h, timeout=timeout)
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return None

    def _fetch_text(self, url, timeout=15, headers=None):
        rsp = self._fetch(url, timeout=timeout, headers=headers)
        if rsp is None:
            return ""
        if hasattr(rsp, "text"):
            return rsp.text or ""
        if hasattr(rsp, "content"):
            return rsp.content.decode("utf-8", "ignore")
        return str(rsp)

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

    # ============== RC4 解密（严格照 YKQ 源码里的 rc4(data,key,1) 复刻）==============
    # YKQ 源码：
    #   function rc4(data, key, t) {
    #       var pwd = key || 'bigon';
    #       if (t == 1) { var data = atob(data); }
    #       var data_length = data.length;
    #       for (i = 0; i < 256; i++) {
    #           key[i] = pwd[i % pwd_length].charCodeAt();
    #           box[i] = i;
    #       }
    #       for (j = i = 0; i < 256; i++) {
    #           j = (j + box[i] + key[i]) % 256;
    #           swap(box[i], box[j]);
    #       }
    #       for (a = j = i = 0; i < data_length; i++) {
    #           a = (a + 1) % 256;
    #           j = (j + box[a]) % 256;
    #           swap(box[a], box[j]);
    #           k = box[((box[a] + box[j]) % 256)];
    #           cipher += chr(data.charCodeAt(i) ^ k);
    #       }
    #       if (t == 1) return decodeURIComponent(cipher);
    #       else return btoa(cipher);
    #   }
    def _rc4_decrypt(self, cipher_b64, key=RC4_KEY):
        """
        输入：Base64 编码的密文串（player 页里 config.url 的值）
        输出：RC4 解密 + URL 解码后的明文字符串（真正的 m3u8 地址）
        """
        raw = base64.b64decode(cipher_b64)

        pwd_bytes = key.encode("utf-8")
        box = list(range(256))
        k = [pwd_bytes[i % len(pwd_bytes)] for i in range(256)]
        j = 0
        for i in range(256):
            j = (j + box[i] + k[i]) % 256
            box[i], box[j] = box[j], box[i]

        out = bytearray()
        a = 0
        j = 0
        for i in range(len(raw)):
            a = (a + 1) % 256
            j = (j + box[a]) % 256
            box[a], box[j] = box[j], box[a]
            kk = box[(box[a] + box[j]) % 256]
            out.append(raw[i] ^ kk)

        # decodeURIComponent(cipher)
        # 用 latin-1（每个字节对应一个字符）再 unquote，
        # 因为 JS 里 String.fromCharCode 是逐字节的，不是按 UTF-8 解。
        s = out.decode("latin-1", "ignore")
        return urllib.parse.unquote(s)

    # ============== 走 player 页拿到真实 m3u8 ==============
    def _get_real_m3u8(self, player_page_url):
        """
        输入：<from>.js 里 MacPlayer.Html 生成的 iframe src 完整 URL
              https://p.iysdq.com/player/?url=<player_aaaa.url>&next=<宿主+link_next>&tittle=<标题>
        过程：
          1. 直接请求这个 player 页
          2. 从返回 HTML 里抓 config.url（Base64 密文）
          3. RC4 解密得到真实 m3u8
        返回：真实 m3u8 地址，失败返回空串
        """
        if not player_page_url:
            return ""
        try:
            self.log("  player page: %s" % player_page_url[:200])

            ana_html = self._fetch_text(player_page_url, headers={
                "User-Agent": PLAYER_UA,
                "Referer": "https://p.iysdq.com/player/",
            })
            if not ana_html:
                self.log("  player 页返回为空")
                return ""

            m = _RE_CONFIG_URL.search(ana_html)
            if not m:
                self.log("  player 页里没找到 config.url")
                return ""

            cipher = m.group(1)
            self.log("  config.url(密文前 80): %s" % cipher[:80])

            real = self._rc4_decrypt(cipher, RC4_KEY)
            self.log("  RC4 解密后: %s" % real[:200])
            return real
        except Exception as e:
            self.log("  _get_real_m3u8 异常: %s" % e)
            return ""

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        for m in _RE_CARD.finditer(html):
            href, title, pic, remark = m.group(1), m.group(2), m.group(3), m.group(4)
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(title)[:100],
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": self._clean(remark),
            })
        self.log("  提取影片: %d 条" % len(videos))
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = _RE_PAGE_INFO.search(html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        return 1

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch_text(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        area = extend.get("area") or ""
        cls  = extend.get("class") or ""
        year = extend.get("year") or ""
        sort = extend.get("sort") or ""

        url = "%s/vodshow/%s-%s-%s-%s-----%s---%s.html" % (
            self.site_url, tid, area, sort, cls,
            str(page) if page > 1 else "",
            year,
        )

        self.log("category: %s" % url)
        html = self._fetch_text(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        pagecount = self._page_count(html)

        total = pagecount * 24
        m = _RE_TOTAL.search(html)
        if m:
            try:
                total = int(m.group(1))
            except Exception:
                pass

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": total,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/vodsearch/-------------.html?wd=%s" % (self.site_url, keyword)
        self.log("search: %s" % url)
        html = self._fetch_text(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
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

        html = self._fetch_text(url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        name = ""
        m = _RE_TITLE.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = name or vod_id

        pic = self.default_pic
        m = _RE_PIC_BJ.search(html)
        if m:
            pic = self._fix_url(m.group(1))

        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html, re.I)
            if m:
                content = self._clean(m.group(1))
        content = INTRO_PREFIX + ("\n" + content if content else "")

        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        director = ""
        m = _RE_DIRECTOR.search(html)
        if m:
            names = _RE_A_TAG.findall(m.group(1))
            director = ", ".join(n.strip() for n in names if n.strip())

        actor = ""
        m = _RE_ACTOR.search(html)
        if m:
            names = _RE_A_TAG.findall(m.group(1))
            actor = ", ".join(n.strip() for n in names if n.strip())

        year, area, status = "", "", ""
        m = _RE_INFO.search(html)
        if m:
            spans = re.findall(r"<span[^>]*>([^<]*)</span>", m.group(1))
            if len(spans) >= 4:
                year, area, status = spans[1], spans[2], spans[3]

        line_forms = []
        for m in _RE_LINE_TAB.finditer(html):
            line_forms.append((m.group(1), self._clean(m.group(2))))

        boxes = _RE_ANTHOLOGY_BOX.findall(html)
        self.log("  线路 tab: %d, 剧集块: %d" % (len(line_forms), len(boxes)))

        play_from = []
        play_url = []
        for i, box in enumerate(boxes):
            eps = _RE_EPISODE.findall(box)
            if not eps:
                continue
            if i < len(line_forms):
                alias = line_forms[i][1]
            else:
                alias = "线路%d" % (i + 1)
            play_from.append(alias)
            play_url.append("#".join("%s$%s" % (self._clean(n), self._fix_url(h))
                                     for h, n in eps))

        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id":       vod_id,
            "vod_name":     name,
            "vod_pic":      pic,
            "vod_content":  content,
            "vod_actor":    actor,
            "vod_director": director,
            "vod_score":    score,
            "vod_year":     year,
            "vod_area":     area,
            "vod_remarks":  status,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # -------- 播放：严格照 <from>.js 里的 MacPlayer.Html 拼接 --------
    # 网页真实路径：
    #   1. player_aaaa.url、player_aaaa.link_next
    #   2. <from>.js 里：
    #        MacPlayer.Html = '<iframe src="https://p.iysdq.com/player/?url='
    #            + MacPlayer.PlayUrl
    #            + '&next=' + (window.location.protocol + '//' + window.location.host + MacPlayer.PlayLinkNext)
    #            + '&tittle=' + document.title.split("-")[0] + '">';
    #      → 拼接得到 player 页 URL
    #   3. 请求这个 player 页
    #   4. 从 HTML 抓 config.url（密文）
    #   5. rc4(config.url, '202306051426239465', 1)
    #      = atob → RC4 → decodeURIComponent
    #   6. 得到真正的 m3u8 地址
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        if play_page in self._play_cache:
            return self._play_cache[play_page]

        html = self._fetch_text(play_page)
        api_url = ""
        link_next = ""
        if html:
            m = _RE_PLAYER.search(html)
            if m:
                try:
                    data = json.loads(m.group(1))
                    api_url = (data.get("url") or "").replace("\\/", "/").replace("&amp;", "&")
                    link_next = data.get("link_next") or ""
                    self.log("  player_aaaa.from=%s" % data.get("from"))
                    self.log("  player_aaaa.url=%s" % api_url[:200])
                    self.log("  player_aaaa.link_next=%s" % link_next)
                except Exception as e:
                    self.log("  player_aaaa 解析失败: %s" % e)

        real_url = ""
        if api_url:
            # ★ 严格照 MacPlayer.Html 拼接 player 页 URL
            # 网页里 next = window.location.protocol + '//' + window.location.host + MacPlayer.PlayLinkNext
            # 即宿主 + link_next。link_next 形如 "/vodplay/177265-4-2.html"
            next_full = self.site_url + link_next if link_next else ""
            # tittle = document.title.split("-")[0]，取播放页标题主名
            tittle = self._clean((_RE_TITLE.search(html).group(1)
                                  if html and _RE_TITLE.search(html) else "")) or "video"

            # 照网页一行一行拼：src="https://p.iysdq.com/player/?url=<PlayUrl>&next=<next_full>&tittle=<tittle>"
            # 注意：网页里是直接字符串拼接，url 参数没有 urlencode，
            # 这里为了保险起见，只对 tittle 做 urlencode（网页里 split("-")[0] 通常不含特殊字符）。
            player_page_url = (
                PLAYER_BASE + "?url=" + api_url
                + "&next=" + next_full
                + "&tittle=" + urllib.parse.quote(tittle, safe="")
            )

            real_url = self._get_real_m3u8(player_page_url)

        if real_url:
            res = {
                "parse": 0,
                "playUrl": "",
                "url": real_url,
                "header": {
                    # 照 cURL 事实：只用真实 UA，不加 Referer，不加 Origin
                    "User-Agent": PLAYER_UA,
                },
            }
            self.log("  => 最终播放地址: %s" % real_url[:200])
        elif api_url:
            res = {
                "parse": 0,
                "playUrl": "",
                "url": api_url,
                "header": {
                    "User-Agent": PLAYER_UA,
                },
            }
            self.log("  => RC4 解密失败，退回 player_aaaa.url: %s" % api_url[:200])
        else:
            res = {
                "parse": 1,
                "playUrl": "",
                "url": play_page,
                "header": {"User-Agent": UA},
            }

        self._play_cache[play_page] = res
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
