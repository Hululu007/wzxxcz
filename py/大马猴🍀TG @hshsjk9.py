# coding=utf-8
"""
SkyKB 影视爬虫 (大马猴影视 skykb.com) - TVBox Python Spider

【网站结构】
1. 站点为 Vue3 SPA，首页 HTML 仅 <div id="app"></div>，不含任何影视数据；
   所有数据均通过 https://skykb.com/api.php/web/* 接口以 JSON 返回。
2. 接口清单（取自 /assets/index-DRlQFQTh.js 中的常量表）：
     GET /api.php/web/index/home                 首页（categories 内含分类与筛选值）
     GET /api.php/web/filter/vod                 分类列表
          ?type_id=22&page=1&sort=hits[&class=&area=&year=&type_name=]
          返回 {code,msg,data[],total,page,limit,pageCount}
     GET /api.php/web/search/index?wd=&page=&limit=
          返回 {code,msg,data[],total,page,limit,pageCount,hasMore}
     GET /api.php/web/vod/get_detail?vod_id=     详情（需签名，否则 vod_play_from 为空）
     GET /api.php/web/internal/search_aggregate?vod_id=  聚合备用线路（需签名）
3. 请求签名（前端 Ze():
     raw = "finger={finger}&id={appId}&nonce={32位hex}&sk={secretKey}&time={13位毫秒}&v=1"
     x-sign = SHA256(raw).hexdigest().upper()
   同时必须携带 x-aid / x-ave / x-time / x-nonc / x-platform: web / x-client。
   【实测】不带签名访问 get_detail，vod_play_from 返回 ""；带签名返回 "lzm3u8$$$Ace"。
4. 播放地址为第三方 CDN 的 m3u8 直链（实测 HTTP 200，可直接播放），无需二次解析。
5. 详情接口的 vod_play_from / vod_play_url 本身已是 TVBox 格式：
     from 之间用 "$$$" 分隔，同一线路的剧集 "第01集$url" 之间用 "#" 分隔。
6. 分页：page 从 1 开始；分类固定每页 24 条（limit=24），pageCount 由接口给出，越界页返回空数组。
"""
import re
import sys
import json
import time
import html as _html
import hashlib
import secrets
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
                print("[skykb]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://skykb.com"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# ---- 前端硬编码的签名参数（源: index-DRlQFQTh.js 中 const ae = {...}）----
APP_ID = "cde75dbd61ce274e07e8ce29"
APP_FINGER = "505a0e62069a061e07698eb4b6327d88"
APP_SECRET = "9b1fccddb6f8e1b385de7e6e736e050144a7f3a208130fff"
APP_VERSION = "1"
CLIENT_ID = "YOUR_PUBLIC_CLIENT_ID"

DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 分类兜底值：真实值来自 index/home 的 categories，接口异常时才使用
_CLASS_FALLBACK = [
    {"type_id": "22", "type_name": "剧集"},
    {"type_id": "23", "type_name": "电影"},
    {"type_id": "24", "type_name": "动漫"},
    {"type_id": "25", "type_name": "综艺"},
]

# 排序：前端 filter/vod 默认 sort=hits，实测 time 可切换到最新
_SORTS = [{"n": "最热", "v": "hits"}, {"n": "最新", "v": "time"}]

# 线路别名兜底（真实显示名取自 get_detail 的 vodplayer[].show）
_LINE_ALIAS = {
    "lzm3u8": "量子M3U8", "Ace": "ACE", "jsm3u8": "极速", "bfzym3u8": "暴风",
    "ikm3u8": "爱坤", "RR": "RR", "BBA": "BB", "NBY": "NB", "rose": "Rose",
    "vwnet": "VW", "YYNB": "YYNB",
}

# 站点 decode_status 取值（前端 On()：status == "2" 抛「线路维护中」）：
#   0 -> 地址为解析后的真实播放地址（可直接播）
#   1 -> 地址为密文串，需前端用 WASM 作服务端解码，TVBox 无法直连
_STATUS_MAINTENANCE = "2"
_STATUS_DECODED = "0"


class Spider(Spider):

    def getName(self):
        return "大马猴影视"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
            "x-platform": "web",
            "x-client": CLIENT_ID,
        }
        self._home_cache = None
        self._last_vod_id = ""
        self.log("init: site=%s" % self.site_url)

    # ================= 签名 =================
    def _sign_headers(self):
        """复现前端签名：SHA256(finger=..&id=..&nonce=..&sk=..&time=..&v=..) 大写"""
        ts = str(int(time.time() * 1000))
        nonce = secrets.token_hex(16)  # 16 字节 -> 32 位 hex，同前端 getRandomValues(16)
        raw = "finger=%s&id=%s&nonce=%s&sk=%s&time=%s&v=%s" % (
            APP_FINGER, APP_ID, nonce, APP_SECRET, ts, APP_VERSION)
        sign = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
        return {
            "x-aid": APP_ID,
            "x-ave": APP_VERSION,
            "x-time": ts,
            "x-nonc": nonce,
            "x-sign": sign,
        }

    # ================= 请求 =================
    def _get_json(self, path, params=None, signed=False, referer=None):
        url = path if path.startswith("http") else self.site_url + path
        if params:
            url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)

        h = dict(self.headers)
        if referer:
            h["Referer"] = referer
        if signed:
            h.update(self._sign_headers())

        try:
            rsp = self.fetch(url, headers=h, timeout=20)
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            else:
                text = str(rsp)
            if not text:
                self.log("empty response: %s" % url)
                return {}
            return json.loads(text)
        except Exception as e:
            self.log("request FAIL %s -> %s" % (url, e))
            return {}

    # ================= 工具 =================
    def _clean(self, s):
        if s is None:
            return ""
        s = str(s)
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = _html.unescape(s)
        s = s.replace("\xa0", " ")
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _join_list(self, v):
        """vod_area / vod_class 在列表接口是数组，在搜索接口是字符串"""
        if isinstance(v, list):
            return ",".join([str(x).strip() for x in v if str(x).strip()])
        return self._clean(v)

    def _fix_pic(self, pic):
        if not pic:
            return DEFAULT_PIC
        pic = str(pic).strip()
        if pic.startswith("//"):
            return "https:" + pic
        if pic.startswith("http"):
            return pic
        if pic.startswith("/"):
            return self.site_url + pic
        return pic

    def _vod_item(self, v):
        """把接口条目转为 TVBox 标准 vod"""
        vod_id = str(v.get("vod_id", "") or "").strip()
        return {
            "vod_id": vod_id,
            "vod_name": self._clean(v.get("vod_name"))[:100],
            "vod_pic": self._fix_pic(v.get("vod_pic")),
            "vod_remarks": self._clean(v.get("vod_remarks")),
            "vod_year": str(v.get("vod_year") or ""),
        }

    def _items_to_list(self, items):
        out = []
        seen = set()
        for v in items or []:
            if not isinstance(v, dict):
                continue
            vod_id = str(v.get("vod_id", "") or "").strip()
            if not vod_id or vod_id == "0" or vod_id in seen:
                continue
            seen.add(vod_id)
            out.append(self._vod_item(v))
        return out

    # ================= 首页配置 =================
    def _load_home(self):
        if self._home_cache is not None:
            return self._home_cache
        d = self._get_json("/api.php/web/index/home")
        data = d.get("data") if isinstance(d, dict) and d.get("code") == 200 else None
        # 接口异常时 data 可能是 null，统一兜成空 dict，避免后续 .get 崩溃
        self._home_cache = data if isinstance(data, dict) else {}
        return self._home_cache

    def _build_classes_and_filters(self):
        """分类与筛选项完全按接口 categories[].filter_options 生成"""
        home = self._load_home()
        cats = home.get("categories") or []
        if not isinstance(cats, list) or not cats:
            return list(_CLASS_FALLBACK), {}

        classes = []
        filters = {}
        for c in cats:
            if not isinstance(c, dict):
                continue
            tid = str(c.get("type_id", "")).strip()
            tname = self._clean(c.get("type_name"))
            if not tid:
                continue
            classes.append({"type_id": tid, "type_name": tname})

            fo = c.get("filter_options") or {}
            fl = []

            cls_vals = fo.get("class") or []
            if cls_vals:
                fl.append({
                    "key": "class", "name": "剧情",
                    "value": [{"n": "全部", "v": ""}] +
                             [{"n": str(x), "v": str(x)} for x in cls_vals],
                })

            area_vals = fo.get("area") or []
            if area_vals:
                fl.append({
                    "key": "area", "name": "地区",
                    "value": [{"n": "全部", "v": ""}] +
                             [{"n": str(x), "v": str(x)} for x in area_vals],
                })

            year_vals = fo.get("year") or []
            if year_vals:
                fl.append({
                    "key": "year", "name": "年份",
                    "value": [{"n": "全部", "v": ""}] +
                             [{"n": str(x), "v": str(x)} for x in year_vals],
                })

            fl.append({"key": "sort", "name": "排序", "value": _SORTS})
            filters[tid] = fl

        return classes, filters

    def homeContent(self, filter=False):
        classes, filters = self._build_classes_and_filters()
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        home = self._load_home()
        videos = []
        seen = set()

        # 首页推荐位：接口 recommend 数组（正片/剧集混排）
        for key in ("recommend", "appCarouselVideos", "webCarouselVideos"):
            for v in (home.get(key) or []):
                if not isinstance(v, dict):
                    continue
                vod_id = str(v.get("vod_id", "") or "")
                if not vod_id or vod_id in seen:
                    continue
                seen.add(vod_id)
                videos.append(self._vod_item(v))

        # 各分类前 6 条补齐
        for c in (home.get("categories") or []):
            for v in (c.get("videos") or []):
                if not isinstance(v, dict):
                    continue
                vod_id = str(v.get("vod_id", "") or "")
                if not vod_id or vod_id in seen:
                    continue
                seen.add(vod_id)
                videos.append(self._vod_item(v))

        return {"list": videos}

    # ================= 分类 =================
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        if page < 1:
            page = 1

        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}

        params = {
            "type_id": str(tid),
            "page": page,
            "sort": extend.get("sort") or "hits",
        }
        # 参数名与前端 In() 完全一致：class / area / year / type_name
        for key in ("class", "area", "year"):
            val = extend.get(key)
            if val and val != "全部":
                params[key] = val

        d = self._get_json("/api.php/web/filter/vod", params)
        if not d or d.get("code") != 200:
            return {"list": [], "page": page, "pagecount": 1,
                    "limit": 24, "total": 0}

        videos = self._items_to_list(d.get("data"))
        pagecount = d.get("pageCount")
        try:
            pagecount = int(pagecount)
        except Exception:
            pagecount = 1
        if pagecount <= 0:
            pagecount = 1

        total = d.get("total")
        try:
            total = int(total)
        except Exception:
            total = len(videos)

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": int(d.get("limit") or 24),
            "total": total,
        }

    # ================= 搜索 =================
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        if page < 1:
            page = 1

        d = self._get_json("/api.php/web/search/index", {
            "wd": key,
            "page": page,
            "limit": 15,
        })
        if not d or d.get("code") != 200:
            return {"list": [], "page": page, "pagecount": 1,
                    "limit": 15, "total": 0}

        videos = self._items_to_list(d.get("data"))
        pagecount = d.get("pageCount")
        try:
            pagecount = int(pagecount)
        except Exception:
            pagecount = 1
        if pagecount <= 0:
            pagecount = 1

        total = d.get("total")
        try:
            total = int(total)
        except Exception:
            total = len(videos)

        return {"list": videos, "page": page, "pagecount": pagecount,
                "limit": int(d.get("limit") or 15), "total": total}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ================= 详情 =================
    def _split_from_url(self, play_from, play_url):
        """按站点格式拆线路：from 用 $$$ 分隔，同一线路的剧集 "第01集$url" 用 # 分隔"""
        froms = [x.strip() for x in str(play_from or "").split("$$$")]
        urls = [x.strip() for x in str(play_url or "").split("$$$")]

        result = []
        for i, f in enumerate(froms):
            if not f or i >= len(urls):
                continue
            eps = []
            for seg in urls[i].split("#"):
                seg = seg.strip()
                if not seg or "$" not in seg:
                    continue
                name, url = seg.split("$", 1)
                name = self._clean(name)
                url = url.strip()
                if not url:
                    continue
                eps.append((name or ("第%d集" % (len(eps) + 1)), url))
            if eps:
                result.append((f, eps))
        return result

    def _player_meta(self, vodplayer):
        """vodplayer[] 是线路定义表：from -> {show显示名, decode_status, decode_mode}"""
        meta = {}
        if not isinstance(vodplayer, list):
            return meta
        for p in vodplayer:
            if not isinstance(p, dict):
                continue
            key = str(p.get("from") or "").strip()
            if not key:
                continue
            meta[key] = {
                "show": self._clean(p.get("show")) or key,
                "status": str(p.get("decode_status", "0")).strip(),
                "mode": str(p.get("decode_mode") or "").strip(),
            }
        return meta

    def _line_kind(self, from_code, meta, eps=None):
        """
        判定一条线路的地址真实形态（以实测样本为准，不臆测）：
          m3u8 -> 已是可直连的 m3u8/mp4 地址
                  （如 lzm3u8: https://v.lzcdn31.com/.../index.m3u8，实测 200）
          page -> 网页地址，需要播放器嗅探
                  （如 RR: https://mh.yichengwlkj.com/drama/57746?episodeNo=1，
                    307 跳转 /pc/... 的 Next.js 页面，页面内无 m3u8）
          code -> 站点密文串，需服务端 WASM 解码
                  （如 Ace: Ace_Net-xxxxxxxx，自身不含协议与 .m3u8）
        """
        sample = ""
        if eps:
            sample = (eps[0][1] if isinstance(eps[0], (list, tuple)) else str(eps[0])).strip()
        low = sample.lower()

        if low.startswith("//"):
            low = "https:" + low

        if low.startswith("http"):
            if ".m3u8" in low or ".mp4" in low:
                return "m3u8"
            return "page"

        if sample:
            return "code"

        # 无样本时退回线路定义表
        m = meta.get(from_code) or {}
        if str(m.get("status", "")) == _STATUS_MAINTENANCE:
            return "code"
        if str(m.get("status", "")) == _STATUS_DECODED and str(m.get("mode", "")) in ("", "client"):
            return "m3u8"
        return "code"

    def detailContent(self, ids):
        if not ids:
            return {"list": []}

        vod_id = str(ids[0]).strip()
        m = re.search(r"(\d+)", vod_id)
        if m:
            vod_id = m.group(1)

        play_page = "%s/play/%s" % (self.site_url, vod_id)
        self._last_vod_id = vod_id

        # 详情必须带签名，否则接口会把 vod_play_from / vod_play_url 置空（已实测）
        d = self._get_json("/api.php/web/vod/get_detail",
                           {"vod_id": vod_id}, signed=True, referer=play_page)
        if not d or d.get("code") != 200 or not isinstance(d.get("data"), list) or not d["data"]:
            self.log("detail empty: %s" % vod_id)
            return {"list": []}

        v = d["data"][0]
        meta = self._player_meta(d.get("vodplayer"))

        name = self._clean(v.get("vod_name")) or vod_id
        pic = self._fix_pic(v.get("vod_pic"))

        # 简介：原文前加固定前缀
        body = self._clean(v.get("vod_content"))
        content = (INTRO_PREFIX + "\n" + body) if body else INTRO_PREFIX

        lines = self._split_from_url(v.get("vod_play_from"), v.get("vod_play_url"))

        # 聚合线路：必须以“追加”方式合并，不能只在主线路为空时兜底。
        # 实测 get_detail 只下发部分线路（如仅 lzm3u8$$$Ace），
        # 而同一播放页调用的 internal/search_aggregate 还带有极速/暴风/爱坤等，
        # 部分影片（如 169386 拜托了冰箱）详情线路甚至为空、聚合却有 52 集。
        agg = self._get_json("/api.php/web/internal/search_aggregate",
                             {"vod_id": vod_id}, signed=True, referer=play_page)
        if agg and agg.get("code") == 200 and isinstance(agg.get("data"), list):
            for a in agg["data"]:
                if not isinstance(a, dict):
                    continue
                if str(a.get("decode_status")) == _STATUS_MAINTENANCE:
                    continue
                one = self._split_from_url(a.get("vod_play_from"), a.get("vod_play_url"))
                if not one:
                    continue
                f, eps = one[0]
                # 同一 from 已由详情提供时，保留详情版本（剧集更全），不覆盖
                if any(f == exist[0] for exist in lines):
                    continue
                meta.setdefault(f, {
                    "show": self._clean(a.get("site_name")) or _LINE_ALIAS.get(f, f),
                    "status": str(a.get("decode_status", "0")),
                    "mode": str(a.get("decode_mode") or ""),
                })
                lines.append((f, eps))

        if not lines:
            self.log("no play line: %s" % vod_id)
            return {"list": []}

        # 排序：m3u8 直链 > 网页(需嗅探) > 密文(不可直连)，保证默认线路能直接播放
        def rank(item):
            kind = self._line_kind(item[0], meta, item[1])
            return {"m3u8": 0, "page": 1}.get(kind, 2)

        lines.sort(key=rank)

        play_from = []
        play_url = []
        for f, eps in lines:
            label = meta[f]["show"] if f in meta else _LINE_ALIAS.get(f, f)
            if label in play_from:  # 同名线路去重，避免 TVBox 线路重复
                label = "%s-%s" % (label, f)
            play_from.append(label)
            play_url.append("#".join("%s$%s" % (n, u) for n, u in eps))

        remarks = self._clean(v.get("vod_remarks"))
        if not remarks:
            remarks = "%d条线路" % len(play_from)

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "type_name": self._clean(v.get("type_name")),
            "vod_year": str(v.get("vod_year") or ""),
            "vod_area": self._join_list(v.get("vod_area")),
            "vod_lang": self._clean(v.get("vod_lang")),
            "vod_remarks": remarks,
            "vod_actor": self._clean(v.get("vod_actor")),
            "vod_director": self._clean(v.get("vod_director")),
            "vod_content": content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ================= 播放 =================
    def _fix_url(self, url):
        """补全协议，并对含非 ASCII（如中文『第01集』目录）的地址做路径编码。
        实测 https://p.bvvvvvvv7f.com/video/baituoliaobingxiang/第01集/index.m3u8
        直接请求会因非 ASCII 报错，编码为 %E7%AC%AC01%E9%9B%86 后返回 200。
        """
        u = (url or "").strip()
        if not u:
            return ""
        if u.startswith("//"):
            u = "https:" + u
        if not u.lower().startswith("http"):
            u = urllib.parse.urljoin(self.site_url + "/", u)
        # 只处理已编码则跳过，避免二次编码
        try:
            u.encode("ascii")
        except UnicodeEncodeError:
            parts = urllib.parse.urlsplit(u)
            path = urllib.parse.quote(parts.path, safe="/%:@&=+$,~*'()")
            query = urllib.parse.quote(parts.query, safe="=&%:@+$,~*'()/?")
            u = urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))
        return u

    def playerContent(self, flag, id, vipFlags):
        """
        按地址真实形态分三种（实测样本）：
          m3u8 -> https://.../index.m3u8 直出，parse=0
          page -> 网页(如 RR 的 mh.yichengwlkj.com/drama/xxx)，parse=1 交 TVBox 嗅探
          code -> 站点密文(如 Ace_Net-xxx)，爬虫内无法解码，退回站点播放页嗅探
        """
        url = (id or "").strip()
        header = {"User-Agent": UA, "Referer": self.site_url + "/"}

        if not url:
            return {"parse": 1, "playUrl": "", "url": "", "header": header}

        if url.lower().startswith("//"):
            url = "https:" + url

        kind = self._line_kind("", {}, [(None, url)])

        if kind == "m3u8":
            return {"parse": 0, "playUrl": "", "url": self._fix_url(url), "header": header}

        if kind == "page":
            # 网页线路：直接嗅探该网页（RR 页面会 307 跳 /pc/...，跟随即可）
            return {"parse": 1, "playUrl": "", "url": self._fix_url(url), "header": header}

        # 密文线路：回退到本站播放页
        if self._last_vod_id:
            page = "%s/play/%s" % (self.site_url, self._last_vod_id)
            return {"parse": 1, "playUrl": "", "url": page, "header": header}

        return {"parse": 1, "playUrl": "", "url": url, "header": header}

    def localProxy(self, param):
        """封面等图片代理"""
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url", "")
            else:
                for pair in str(param).split("&"):
                    if "=" in pair:
                        k, val = pair.split("=", 1)
                        if k == "url":
                            url = val
            if not url:
                return [200, "image/jpeg", b"", ""]

            if "%" in url:
                url = urllib.parse.unquote(url)
            url = self._fix_pic(url)

            rsp = self.fetch(url, headers={
                "User-Agent": UA,
                "Referer": self.site_url + "/",
                "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
            }, timeout=20)
            content = rsp.content
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return ".m3u8" in u or ".mp4" in u

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
