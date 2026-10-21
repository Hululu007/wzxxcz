# coding=utf-8
import re
import sys
import json
import time
import html as _html
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
            return self._session
        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout)
            r.encoding = 'utf-8'
            return r
        def log(self, *a, **kw):
            pass
    Spider = _BaseSpider

HOST = 'https://www.gljade.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
DEFAULT_PIC = HOST + '/favicon.ico'
INTRO_PREFIX = '🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！'

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "6", "type_name": "动作片"},
    {"type_id": "7", "type_name": "喜剧片"},
    {"type_id": "8", "type_name": "爱情片"},
    {"type_id": "9", "type_name": "科幻片"},
    {"type_id": "10", "type_name": "剧情片"},
    {"type_id": "11", "type_name": "战争片"},
    {"type_id": "41", "type_name": "动画片"},
    {"type_id": "12", "type_name": "记录片"},
    {"type_id": "39", "type_name": "恐怖片"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "13", "type_name": "国产剧"},
    {"type_id": "14", "type_name": "香港剧"},
    {"type_id": "15", "type_name": "韩国剧"},
    {"type_id": "16", "type_name": "欧美剧"},
    {"type_id": "22", "type_name": "台湾剧"},
    {"type_id": "21", "type_name": "日本剧"},
    {"type_id": "20", "type_name": "泰国剧"},
    {"type_id": "23", "type_name": "海外剧"},
    {"type_id": "3", "type_name": "综艺片"},
    {"type_id": "25", "type_name": "大陆综艺"},
    {"type_id": "26", "type_name": "日韩综艺"},
    {"type_id": "27", "type_name": "港台综艺"},
    {"type_id": "28", "type_name": "欧美综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "29", "type_name": "国产动漫"},
    {"type_id": "30", "type_name": "日本动漫"},
    {"type_id": "42", "type_name": "港台动漫"},
    {"type_id": "31", "type_name": "欧美动漫"},
    {"type_id": "43", "type_name": "海外动漫"},
]

_YEARS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)]
_AREAS = [{"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"}, 
          {"n": "美国", "v": "美国"}, {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"}, {"n": "泰国", "v": "泰国"}]
_SORTS = [{"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}]

FILTERS = {c["type_id"]: [
    {"key": "class", "name": "分类", "value": [{"n": "全部", "v": ""}]},
    {"key": "area", "name": "地区", "value": _AREAS},
    {"key": "year", "name": "年份", "value": _YEARS},
    {"key": "sort_field", "name": "排序", "value": _SORTS},
] for c in CLASSES}

# 精确抓取影片卡片，排除分类导航的 /video/6.html
_RE_CARD = re.compile(r'<a[^>]*?href="(/video/\d+\.html)"[^>]*?title="([^"]*)"[^>]*?>', re.S | re.I)
_RE_PIC = re.compile(r'<img[^>]*?data-src="([^"]+)"', re.I)
_RE_REMARKS = re.compile(r'<span[^>]*?class="[^"]*?text-red[^"]*?"[^>]*?>([^<]+)</span>', re.I)

_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_OG_IMG = re.compile(r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)', re.I)
_RE_INTRO = re.compile(r'<div[^>]*class="[^"]*?desc[^"]*?"[^>]*?>([\s\S]*?)</div>', re.I)
_RE_DIRECTOR = re.compile(r'导演\s*[:：]\s*([^\s\n主]{1,40})')
_RE_ACTOR = re.compile(r'主演\s*[:：]\s*([^\n]{1,100})')

# 播放线路和剧集，专治 /video/779291/1/1.html 这种格式
_RE_PLAY_LIST = re.compile(r'<a[^>]*?href="(/video/\d+/\d+/\d+\.html)"[^>]*?>([^<]+)</a>', re.S | re.I)

# 视频源提取
_RE_PLAYER = re.compile(r'player_aaaa\s*=\s*(\{[\s\S]*?\})', re.I)

def unescape_url(u):
    if not u: return ""
    u = u.replace("\\/", "/").replace("\\u0026", "&").replace("\\u003d", "=")
    return _html.unescape(u).strip()

class Spider(Spider):
    def getName(self):
        return "火龙果影视"

    def init(self, extend=""):
        self.site_url = HOST
        self.headers = {
            "User-Agent": UA,
            "Referer": self.site_url + "/",
        }

    def _fetch(self, url):
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=15)
            return rsp.text if hasattr(rsp, "text") else rsp.content.decode("utf-8", "ignore")
        except Exception as e:
            self.log("fetch err", e)
            return ""

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        
        # 拼接请求 URL
        # 该站一级分类是 /cat/1.html，二级分类是 /medialist/id/6.html
        url = f"{self.site_url}/cat/{tid}.html" if str(tid) in ('1', '2', '3', '4') else f"{self.site_url}/medialist/id/{tid}.html"
        if page > 1:
            url = f"{self.site_url}/cat/{tid}-{page}.html" if str(tid) in ('1', '2', '3', '4') else f"{self.site_url}/medialist/id/{tid}-{page}.html"
            
        # 如果选择了筛选参数，加上参数（苹果CMS一般通用）
        if extend:
            params = []
            for k, v in extend.items():
                if v and k != 'class':
                    if k == 'sort_field':
                        params.append(f"order={v}")
                    elif k == 'area':
                        params.append(f"area={urllib.parse.quote(v)}")
                    elif k == 'year':
                        params.append(f"year={v}")
            if params:
                url += ("&" if "?" in url else "?") + "&".join(params)

        html = self._fetch(url)
        
        # 提取影片
        videos = []
        for m in re.finditer(r'<a[^>]*?href="(/video/\d+\.html)"[^>]*?title="([^"]*)"[^>]*?>([\s\S]*?)</a>', html, re.I):
            href, name, inner = m.groups()
            if len(name) > 20 or "片" in name or "综艺" in name or "动漫" in name:
                # 过滤掉误抓的分类链接
                if re.search(r'/\d+\.html', href) and href.split('/')[-1].split('.')[0] in ('6','7','8','9','10','11','12','41','39'):
                    continue
            
            pic = ""
            m_pic = _RE_PIC.search(inner)
            if m_pic: pic = m_pic.group(1)
            if not pic:
                m_pic = re.search(r'src="([^"]+)"', inner)
                if m_pic: pic = m_pic.group(1)
                
            rem = ""
            m_rem = _RE_REMARKS.search(inner)
            if m_rem: rem = m_rem.group(1)
            
            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": self._fix_url(pic),
                "vod_remarks": rem
            })
            
        return {"list": videos, "page": page, "pagecount": 999, "limit": 24, "total": 9999}

    def detailContent(self, ids):
        vod_id = ids[0]
        url = self._fix_url(vod_id)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        name = ""
        h1s = [re.sub(r'<[^>]+>', '', x).strip() for x in _RE_H1.findall(html)]
        if h1s:
            name = h1s[0]
            
        pic = DEFAULT_PIC
        m = _RE_OG_IMG.search(html)
        if m: pic = m.group(1)

        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        
        director = actor = ""
        plain = re.sub(r'<[^>]+>', ' ', html)
        m = _RE_DIRECTOR.search(plain)
        if m: director = m.group(1).strip()
        m = _RE_ACTOR.search(plain)
        if m: actor = m.group(1).strip()

        # 解析剧集：/video/779291/1/1.html
        groups = {}
        for m in _RE_PLAY_LIST.finditer(html):
            href, ep_name = m.groups()
            ep_name = ep_name.strip()
            # 从 URL 提取线路号
            mo = re.search(r'/video/\d+/(\d+)/\d+\.html', href)
            origin = "线路" + mo.group(1) if mo else "线路1"
            
            full_url = href if href.startswith("http") else self.site_url + href
            groups.setdefault(origin, []).append(f"{ep_name}${full_url}")

        play_from = []
        play_url = []
        for o in groups.keys():
            play_from.append(o)
            play_url.append("#".join(groups[o]))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": INTRO_PREFIX + "\n" + content if content else INTRO_PREFIX,
            "vod_director": director,
            "vod_actor": actor,
            "vod_remarks": f"{len(groups)}条线路",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    def playerContent(self, flag, id, vipFlags):
        play_page = self._fix_url(id)
        html = self._fetch(play_page)
        
        player_data = ""
        m = _RE_PLAYER.search(html)
        if m:
            player_data = m.group(1)
            
        api_url = ""
        if player_data:
            m2 = re.search(r'"url"\s*:\s*"([^"]+)"', player_data)
            if m2:
                api_url = unescape_url(m2.group(1))
                
        if api_url:
            if api_url.startswith("/"):
                api_url = self.site_url + api_url
            return {
                "parse": 0,
                "playUrl": "",
                "url": api_url,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"}
            }
            
        return {"parse": 1, "playUrl": "", "url": play_page, "header": {"User-Agent": UA}}

    def _fix_url(self, url):
        if not url: return ""
        if url.startswith("//"): return "https:" + url
        if url.startswith("http"): return url
        if url.startswith("/"): return self.site_url + url
        return self.site_url + "/" + url

    def searchContent(self, key, quick, pg="1"):
        return {"list": []}

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False
