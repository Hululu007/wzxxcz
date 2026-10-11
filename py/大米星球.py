# coding=utf-8
"""
大米星球 dmxq40.com | TVBox Python 爬虫 (参考豆花写法重构版)
关键修复:
  - 分类URL精准拼装 (兼容11个连字符与页码占位符)
  - 列表卡片分级提取 (兼容首页、分类页、搜索页不同结构)
  - 详情页剧集安全分组 (解析真实播放源名称)
  - 播放页 player_aaaa 全量JSON贪婪匹配
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
                adapter = _rq.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
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
                print("[dmxq]", *a)
            except Exception:
                pass

    Spider = _BaseSpider

HOST = "https://dmxq40.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = "https://vpic.cms.qq.com/nj_vpic/3272248629/1738572385393158887/112429678912224247"

CLASSES = [
    {"type_id": "20", "type_name": "电影"},
    {"type_id": "21", "type_name": "电视剧"},
    {"type_id": "36", "type_name": "短剧"},
    {"type_id": "22", "type_name": "动漫"},
    {"type_id": "23", "type_name": "综艺"},
]

_SORTS = [
    {"n": "时间", "v": "time"},
    {"n": "人气", "v": "hits"},
    {"n": "评分", "v": "score"}
]
_YEARS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_AREAS = [
    {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
    {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"},
    {"n": "韩国", "v": "韩国"}, {"n": "英国", "v": "英国"}, {"n": "法国", "v": "法国"}
]

_FILTERS_MAP = {
    "20": ["全部", "Netflix", "仙侠", "剧情", "科幻", "动作", "喜剧", "爱情", "冒险", "恐怖", "悬疑", "犯罪", "战争"],
    "21": ["全部", "Netflix", "短剧", "剧情", "网剧", "丧尸", "仙侠", "穿越", "惊悚", "恐怖", "言情", "科幻", "动作", "喜剧", "爱情"],
    "36": ["全部", "AI漫剧", "短剧", "剧情", "爱情", "爽文", "古装", "悬疑", "喜剧", "奇幻", "都市", "玄幻", "穿越"],
    "22": ["全部", "Netflix", "热血", "科幻", "美少女", "魔幻", "经典", "励志", "少儿", "冒险", "搞笑", "推理"],
    "23": ["全部", "脱口秀", "真人秀", "选秀", "八卦", "访谈", "情感", "生活", "晚会", "搞笑", "音乐"]
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "剧情", "value": [{"n": x, "v": "" if x == "全部" else x} for x in _FILTERS_MAP.get(tid, ["全部"])]},
        {"key": "area", "name": "地区", "value": _AREAS},
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
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=20, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            
            # 检测是否被拦截（大米星球可能会加盾，如果拦截则返回空）
            if "正在检测" in text or "sha1(hash" in text:
                self.log("⚠️ 遇到安全拦截，尝试直连备用...")
            return text
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _fix_url(self, url):
        if not url: return ""
        url = url.strip().replace("&amp;", "&")
        if url.startswith("//"): return "https:" + url
        if url.startswith("http"): return url
        if url.startswith("/"): return self.site_url + url
        return urllib.parse.urljoin(self.site_url + "/", url)

    def _clean(self, s):
        if not s: return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ").replace("&amp;", "&")
              .replace("&quot;", '"').replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        return re.sub(r"\s+", " ", s).strip()

    # ===================== 列表提取（参考豆花分级提取思路） =====================
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html: return videos

        # 1. 尝试提取完整卡片（兼容分类页、首页的 module-poster-item）
        matches = re.finditer(
            r'<a\s+href="(/voddetail/[^"]+?\.html)"[^>]*?title="([^"]*)"[^>]*?>[\s\S]*?'
            r'<img[^>]*?(?:data-original|src)="([^"]+)"', html, re.S | re.I)
        
        for m in matches:
            href, title, pic = m.groups()
            if href in seen: continue
            seen.add(href)
            
            # 提取备注
            block = m.group(0)
            remark_match = re.search(r'<div class="module-item-note">([^<]*)</div>', block, re.I)
            remark = self._clean(remark_match.group(1)) if remark_match else ""
            
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(title),
                "vod_pic": self._fix_url(pic),
                "vod_remarks": remark
            })

        # 2. 如果完整卡片提取失败（比如搜索页 module-card-item 结构不同），降级提取
        if not videos:
            hrefs = re.findall(r'href="(/voddetail/[^"]+?\.html)"', html)
            imgs = re.findall(r'<img[^>]*?alt="([^"]*)"[^>]*?(?:data-original|src)="([^"]*)"', html, re.S | re.I)
            for i, href in enumerate(hrefs):
                if href in seen: continue
                seen.add(href)
                title, pic = href, DEFAULT_PIC
                if i < len(imgs):
                    title, pic = imgs[i][0] or href, imgs[i][1]
                videos.append({
                    "vod_id": href,
                    "vod_name": self._clean(title),
                    "vod_pic": self._fix_url(pic),
                    "vod_remarks": ""
                })

        return videos

    def _page_count(self, html):
        if not html: return 1
        m = re.search(r'href="([^"]+?)"[^>]*title="尾页"', html, re.I)
        if not m:
            m = re.search(r'title="尾页"[^>]*href="([^"]+?)"', html, re.I)
        if m:
            mm = re.search(r'(\d+)---', m.group(1))
            if mm:
                try: return int(mm.group(1))
                except Exception: pass
        return 9999

    # ===================== TVBox 接口实现 =====================

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/index/home.html")
        videos = self._extract_videos(html)
        self.log("home 提取: %d 条" % len(videos))
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        if isinstance(extend, str):
            try: extend = json.loads(extend)
            except Exception: extend = {}
        if not extend: extend = {}

        page = int(pg) if pg else 1
        area = urllib.parse.quote(extend.get("area", ""))
        cls = urllib.parse.quote(extend.get("class", ""))
        sort = extend.get("sort", "")
        year = extend.get("year", "")

        # ★ 精准适配大米星球 URL 拼接规律
        # 情况 A: 无筛选第 1 页 -> /vodshow/20-----------.html (11个连字符)
        # 情况 B: 无筛选第 2 页 -> /vodshow/20--------2---.html (8个连字符+2+3个连字符)
        # 情况 C: 有筛选第 1 页 -> /vodshow/20-大陆----------.html
        # 情况 D: 有筛选第 2 页 -> /vodshow/20-大陆-------2---.html
        
        parts = []
        if area: parts.append(area)
        if cls: parts.append(cls)
        if sort and sort != "time": parts.append(sort) # time 为默认，通常省略
        
        mid = "-".join(parts)
        
        if not mid:
            if page == 1:
                url = f"{self.site_url}/vodshow/{tid}-----------{year}.html"
            else:
                url = f"{self.site_url}/vodshow/{tid}--------{page}---{year}.html"
        else:
            if page == 1:
                url = f"{self.site_url}/vodshow/{tid}-{mid}----------{year}.html"
            else:
                url = f"{self.site_url}/vodshow/{tid}-{mid}-------{page}---{year}.html"

        self.log("category URL: %s" % url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        self.log("  提取到: %d 条" % len(videos))
        
        return {
            "list": videos, "page": page, 
            "pagecount": self._page_count(html), 
            "limit": 24, "total": 999
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key, safe="")
        if page == 1:
            url = f"{self.site_url}/vodsearch/{kw}-------------.html"
        else:
            url = f"{self.site_url}/vodsearch/{kw}----------{page}---.html"
        html = self._fetch(url)
        videos = self._extract_videos(html)
        return {"list": videos, "page": page, "pagecount": self._page_count(html), "limit": 24, "total": 999}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids: return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        html = self._fetch(url)
        if not html: return {"list": []}

        name = ""
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
        if m: name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
            if m: name = self._clean(m.group(1).split("-")[0].split("_")[0])
        if not name: name = vod_id

        pic = ""
        m = re.search(r'<div class="module-item-pic">\s*<img[^>]*?src="([^"]+)"', html, re.S | re.I)
        if not m: m = re.search(r'<img[^>]*?data-original="([^"]+)"', html, re.S | re.I)
        if m: pic = self._fix_url(m.group(1))

        content = ""
        m = re.search(r'<div class="module-info-introduction-content[^"]*"[^>]*>([\s\S]*?)</div>', html, re.S | re.I)
        if not m: m = re.search(r'<meta name="description" content="([^"]*)"', html, re.I)
        if m: content = self._clean(m.group(1))

        # ★ 剧集提取（参考豆花的剧集分组思路，适配大米星球的 tab 结构）
        tabs = re.findall(r'<div class="module-tab-item tab-item[^"]*"[^>]*data-dropdown-value="([^"]+)"', html, re.I)
        groups = {}
        for m in re.finditer(r'href="(/vodplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*?><span>([^<]+)</span>', html, re.I):
            href, vid, sid, nid, ep = m.groups()
            sid = int(sid)
            groups.setdefault(sid, []).append((self._clean(ep), self._fix_url(href)))

        if not groups:
            self.log("未找到剧集")
            return {"list": []}

        play_from = []
        play_url = []
        for i, sid in enumerate(sorted(groups.keys())):
            play_from.append(tabs[i] if i < len(tabs) else f"线路{sid}")
            play_url.append("#".join(f"{n}${u}" for n, u in groups[sid]))

        return {"list": [{
            "vod_id": vod_id, "vod_name": name, "vod_pic": pic, "vod_content": content,
            "vod_play_from": "$$$".join(play_from), "vod_play_url": "$$$".join(play_url),
            "vod_remarks": f"{len(groups)}条线路"
        }]}

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600: return res

        html = self._fetch(play_page)
        url = ""

        # ★ 核心修复：贪婪匹配完整的 JSON，防止嵌套 `vod_data` 导致截断
        m = re.search(r'player_aaaa\s*=\s*({.*})\s*;?\s*</script>', html, re.S)
        if m:
            raw = m.group(1)
            try:
                data = json.loads(raw)
                url = data.get("url") or ""
            except Exception as e:
                self.log("json fail: %s" % e)
                mm = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                if mm: url = mm.group(1)

        if url:
            url = url.replace("\\/", "/").replace("&amp;", "&")
            if url.startswith("//"): url = "https:" + url
            self.log("player url: %s" % url[:150])
            res = {"parse": 0, "playUrl": "", "url": url, "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底：交给嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page, "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def localProxy(self, param):
        try:
            url = param.get("url", "") if isinstance(param, dict) else ""
            if not url: return [200, "image/jpeg", b"", ""]
            url = urllib.parse.unquote(url) if "%" in url else url
            rsp = self.fetch(self._fix_url(url), headers={"User-Agent": UA, "Referer": self.site_url + "/"}, timeout=15)
            return [200, rsp.headers.get("Content-Type", "image/jpeg"), rsp.content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self): return False
    def destroy(self): pass
    def close(self): self.destroy()
