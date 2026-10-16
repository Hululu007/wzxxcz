# coding=utf-8
"""
影视大全 iysdq1.com | TVBox Python 爬虫
严格依据网站真实源码 + F12 抓包编写：
  - 分类 URL：/vodshow/{tid}-{area}-{sort}-{cls}-----{pg}---{year}.html
  - 搜索 URL：/vodsearch/-------------.html?wd={关键词}
  - 详情页线路 tab 用 data-form 标识，与 anthology-list-box 按序对应
  - 剧集 URL：/vodplay/{id}-{sid}-{nid}.html
  - 播放：player_aaaa.url = https://svip.xgplay17.com/{path}/index.m3u8
          真实可播 CDN  = https://vip17.jimxtc.com/{path}/index.m3u8
          （{path} 完全相同，已用浏览器验证 vip17 可直播）
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
                print("[iysdq]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.iysdq1.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
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

_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)


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

    # -------- 播放 --------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        if play_page in self._play_cache:
            return self._play_cache[play_page]

        html = self._fetch_text(play_page)
        api_url = ""
        if html:
            m = _RE_PLAYER.search(html)
            if m:
                try:
                    data = json.loads(m.group(1))
                    api_url = (data.get("url") or "").replace("\\/", "/").replace("&amp;", "&")
                    self.log("  player_aaaa.url: %s" % api_url[:180])
                except Exception as e:
                    self.log("  player_aaaa 解析失败: %s" % e)

        real_url = ""
        if api_url:
            real_url = self._get_playable_url(api_url, referer=play_page)

        if real_url:
            res = {
                "parse": 0,
                "playUrl": "",
                "url": real_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": play_page,
                },
            }
            self.log("  => 播放地址: %s" % real_url[:180])
        else:
            res = {
                "parse": 1,
                "playUrl": "",
                "url": play_page,
                "header": {
                    "User-Agent": UA,
                    "Referer": play_page,
                },
            }

        self._play_cache[play_page] = res
        return res

    def _get_playable_url(self, api_url, referer=None):
        """
        已知事实（来自 F12 + 浏览器验证）：
          player_aaaa.url = https://svip.xgplay17.com/{path}/index.m3u8
          真实可播直链     = https://vip17.jimxtc.com/{path}/index.m3u8
          {path} 完全相同，vip17.jimxtc.com 在浏览器里可直接播放。
        策略：
          1) 试 302 Location
          2) 换域名到 vip17.jimxtc.com，实际请求确认响应含 #EXTM3U
          3) 都失败则返回原 url
        """
        headers = {"User-Agent": UA, "Accept": "*/*"}
        if referer:
            headers["Referer"] = referer

        # 路径1：请求原 url，看能否拿 Location
        loc = ""
        try:
            rsp = self.fetch(api_url, headers=headers, timeout=15,
                             allow_redirects=False)
            if hasattr(rsp, "headers"):
                loc = rsp.headers.get("Location", "") or rsp.headers.get("location", "")
        except TypeError:
            try:
                rsp = self.fetch(api_url, headers=headers, timeout=15)
                final = getattr(rsp, "url", "") or ""
                if final and final != api_url:
                    self.log("  fetch 跟随跳转最终: %s" % final[:180])
                    return final
            except Exception as e:
                self.log("  请求 api_url 失败: %s" % e)
        except Exception as e:
            self.log("  请求 api_url 失败: %s" % e)

        if loc:
            if loc.startswith("//"):
                loc = "https:" + loc
            loc = loc.replace("&amp;", "&")
            self.log("  302 Location: %s" % loc[:180])
            return loc

        # 路径2：域名替换到 vip17.jimxtc.com，实际请求校验 #EXTM3U
        try:
            parsed = urllib.parse.urlparse(api_url)
            path = parsed.path
            if parsed.query:
                path += "?" + parsed.query
            candidate = "https://vip17.jimxtc.com%s" % path
            self.log("  尝试直连 CDN: %s" % candidate[:180])
            try:
                rsp2 = self.fetch(candidate, headers=headers, timeout=10)
                text = ""
                if hasattr(rsp2, "text"):
                    text = rsp2.text or ""
                if not text and hasattr(rsp2, "content"):
                    text = rsp2.content.decode("utf-8", "ignore")
                if "#EXTM3U" in text:
                    self.log("  ✓ CDN 返回 #EXTM3U")
                    return candidate
                else:
                    self.log("  ✗ CDN 无 #EXTM3U")
            except Exception as e:
                self.log("  ✗ 校验 CDN 失败: %s" % e)
        except Exception as e:
            self.log("  域名替换失败: %s" % e)

        # 路径3：兜底
        self.log("  兜底返回原 api_url")
        return api_url

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
