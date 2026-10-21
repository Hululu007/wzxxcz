# -*- coding: utf-8 -*-
"""
看剧 kanju.ai | TVBox Python 爬虫 
关键:
  - HMAC-SHA256 请求签名 (timestamp + nonce)
  - 主备域名自动切换
  - 播放多级兜底: yjm3u8 直链 -> yjapi -> resolve-line
"""
import sys
import json
import time
import math
import hmac
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
            method = kw.pop('method', 'GET').upper()
            data = kw.pop('data', None)
            if method == 'POST':
                r = self._sess.post(url, headers=headers, data=data,
                                    timeout=timeout, **kw)
            else:
                r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[kanju]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOSTS = ["https://kanju.ai", "https://kanju20.com"]
KEY = "557d0e4ae929f438da6bd84412374e6086b8af09b3fed54bf22601d5bf8c54a0"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
YJ = "https://zy.baipiaozhe.com/v1/playback/yjm3u8/%s.m3u8"
YJ_API = "https://zy.baipiaozhe.com/v1/playback/yjapi/%s"
CLIENT = {
    "x-ai-movie-client-name": "dianyingtiantang-frontend",
    "x-ai-movie-client-version": "1.0.0",
    "x-ai-movie-build-version": "dianyingtiantang-v2026.08.11.1-8cbb0b0d407e-672e67d62528",
    "x-ai-movie-protocol-version": "2026-07-05.library-v2.playback-v1",
}

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CATEGORIES = {
    "movie": "电影", "series": "电视剧", "short_drama": "短剧",
    "anime": "动漫", "variety": "综艺", "documentary": "纪录片",
}

GENRES = {
    "movie": ["动作", "冒险", "剧情", "喜剧", "奇幻", "古装", "家庭", "科幻"],
    "series": ["动作", "冒险", "剧情", "刑侦", "古装", "历史", "台剧", "悬疑"],
    "short_drama": ["剧情", "动作", "反转爽剧", "古装仙侠", "喜剧", "女频恋爱", "家庭", "年代"],
    "anime": ["热血", "冒险", "奇幻", "日本动漫", "国产动漫", "爆笑", "武侠", "儿童"],
    "variety": ["大陆综艺", "真人秀", "情感", "爱情", "社交观察"],
    "documentary": ["历史", "纪录片"],
}

_SORTS = [
    {"n": "热门", "v": "trending"},
    {"n": "最新", "v": "latest"},
    {"n": "评分", "v": "rating"},
]


class Spider(Spider):

    def getName(self):
        return "看剧"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.hosts = list(self.extend.get("hosts") or HOSTS)
        self._hi = 0
        self.headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self._host() + "/",
        }
        self._hv = None
        self._hv_t = 0
        self._sc = {}
        self._sc_t = {}

        # 探测可用域名
        for i, h in enumerate(self.hosts):
            try:
                r = self.fetch(h, headers={"User-Agent": UA}, timeout=15)
                if getattr(r, "status_code", None) == 200:
                    self._hi = i
                    break
            except Exception:
                continue
        self.log("init: host=%s" % self._host())
        return ""

    # ---------------- 基础工具 ----------------

    def _host(self):
        return self.hosts[getattr(self, "_hi", 0)]

    def _sign(self, method, path):
        ts = str(int(time.time() * 1000))
        nonce = secrets.token_hex(16)
        msg = "%s\n%s\n%s\n%s" % (method, path, ts, nonce)
        sig = hmac.new(KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return ts, nonce, sig

    def _fetch(self, url, headers=None, timeout=15, method="GET", data=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            if method.upper() == "POST":
                rsp = self.fetch(url, headers=h, timeout=timeout,
                                 method="POST", data=data)
            else:
                rsp = self.fetch(url, headers=h, timeout=timeout)
            return rsp
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return None

    def _req(self, method, path, body=None):
        for _ in range(len(self.hosts)):
            host = self._host()
            try:
                ts, nonce, sig = self._sign(method, path)
                hdrs = {
                    "User-Agent": UA, "Accept": "application/json",
                    "Referer": host + "/",
                    "x-ai-movie-timestamp": ts, "x-ai-movie-nonce": nonce,
                    "x-ai-movie-signature": sig,
                }
                hdrs.update(CLIENT)
                url = host + path
                if body is not None:
                    hdrs["Content-Type"] = "application/json"
                    rsp = self._fetch(url, headers=hdrs, timeout=10,
                                      method="POST", data=json.dumps(body))
                else:
                    rsp = self._fetch(url, headers=hdrs, timeout=10)

                if rsp is None:
                    raise RuntimeError("rsp is None")
                code = getattr(rsp, "status_code", 0)
                if code in (200, 201):
                    try:
                        return rsp.json()
                    except Exception:
                        txt = getattr(rsp, "text", "") or ""
                        return json.loads(txt) if txt else {}
                self.log("req %s %s -> HTTP %s" % (method, path, code))
            except Exception as e:
                self.log("req FAIL %s %s -> %s" % (method, path, e))
            self._hi = (self._hi + 1) % len(self.hosts)
            time.sleep(1)
        return {}

    def _fix_url(self, url):
        if not url:
            return ""
        url = str(url).strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self._host() + url
        return urllib.parse.urljoin(self._host() + "/", url)

    def _clean(self, s):
        if not s:
            return ""
        s = str(s)
        s = s.replace("&nbsp;", " ").replace("\xa0", " ")
        s = (s.replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        return s.strip()

    # ---------------- 内容 ----------------

    def _vod(self, c):
        if not isinstance(c, dict):
            return {}
        return {
            "vod_id": c.get("id", ""),
            "vod_name": self._clean(c.get("title", "")),
            "vod_pic": self._fix_url(c.get("poster_url", "")),
            "vod_remarks": self._clean(c.get("remarks") or str(c.get("year") or "")),
            "vod_year": str(c.get("year") or ""),
            "vod_area": self._clean(c.get("area") or ""),
            "vod_actor": "/".join((c.get("actors") or [])[:3]),
            "vod_director": "/".join((c.get("directors") or [])[:2]),
        }

    def homeContent(self, filter=False):
        cls = []
        for k, v in CATEGORIES.items():
            cls.append({
                "type_id": k, "type_name": v,
                "subs": [{"type_id": "%s:%s" % (k, g), "type_name": g}
                         for g in GENRES.get(k, [])],
            })
        filters = {}
        for k in CATEGORIES:
            filters[k] = [
                {"key": "sort", "name": "排序", "value": _SORTS},
                {"key": "genre", "name": "类型",
                 "value": [{"n": "全部", "v": ""}] +
                          [{"n": g, "v": g} for g in GENRES.get(k, [])]},
            ]
        return {"class": cls, "filters": filters, "list": []}

    def homeVideoContent(self):
        now = time.time()
        if self._hv and (now - self._hv_t < 300):
            return self._hv

        seen, lst = set(), []
        paths = [
            "/v1/feed/home",
            "/v1/browse/catalog?kind=movie&sort=trending&window=day&page=1&limit=40",
            "/v1/browse/catalog?kind=series&sort=trending&window=day&page=1&limit=40",
            "/v1/browse/catalog?kind=short_drama&sort=trending&window=day&page=1&limit=40",
        ]
        for p in paths:
            j = self._req("GET", p)
            if not j:
                continue
            for s in (j.get("sections") or []):
                for c in (s.get("cards") or []):
                    v = self._vod(c)
                    vid = v.get("vod_id")
                    if vid and vid not in seen:
                        seen.add(vid)
                        lst.append(v)
            for c in (j.get("cards") or []):
                v = self._vod(c)
                vid = v.get("vod_id")
                if vid and vid not in seen:
                    seen.add(vid)
                    lst.append(v)

        self._hv, self._hv_t = {"list": lst}, now
        self.log("home: %d 条" % len(lst))
        return self._hv

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        pn = 1
        try:
            pn = max(int(str(pg)), 1)
        except Exception:
            pass

        # 解析 extend
        ext = {}
        if isinstance(extend, dict):
            ext = extend
        elif isinstance(extend, str) and extend:
            try:
                ext = json.loads(extend)
            except Exception:
                ext = {}

        cat, gen = str(tid), ""
        if ":" in cat:
            cat, gen = cat.split(":", 1)
        if cat not in CATEGORIES:
            cat = "movie"

        # 筛选条件覆盖
        if isinstance(ext, dict):
            gen = ext.get("genre") or gen
            sort = ext.get("sort") or "trending"
        else:
            sort = "trending"

        qs = ["kind=%s" % cat]
        if gen:
            qs.append("genre=%s" % urllib.parse.quote(gen))
        if sort:
            qs.append("sort=%s" % urllib.parse.quote(str(sort)))
        qs.append("page=%d" % pn)
        qs.append("limit=40")
        path = "/v1/browse/catalog?" + "&".join(qs)

        self.log("category: %s" % path)
        j = self._req("GET", path)
        cards = j.get("cards") or []
        total = (j.get("pagination") or {}).get("total", 0) or 0
        pagecount = max(math.ceil(total / 40.0), 1) if total else 1

        return {
            "page": pn, "pagecount": pagecount, "limit": 40,
            "total": total or len(cards),
            "list": [self._vod(c) for c in cards if c],
        }

    def detailContent(self, ids):
        if isinstance(ids, list):
            vid = ids[0] if ids else ""
        else:
            vid = str(ids) if ids else ""
        vid = str(vid).split("/")[0].strip()
        if not vid:
            return {"list": []}

        self.log("detail: %s" % vid)
        d = self._req("GET", "/v1/catalog/%s" % vid)
        if not d:
            return {"list": []}

        eps = d.get("episodes") or []
        urls = []
        for e in eps:
            t = e.get("token")
            if not t:
                continue
            ep_name = (e.get("title")
                       or ("第%s集" % (e.get("number") or len(urls) + 1)))
            urls.append("%s$%s" % (ep_name, t))

        play_from, play_url = "kanju", "#".join(urls)

        # 多线路：用第一集 token 解析线路名
        if eps and urls:
            tok0 = eps[0].get("token")
            if tok0:
                rj = self._req("GET", "/v1/playback/resolve/%s" % tok0)
                names = []
                for lo in (rj.get("line_options") or []):
                    n = (lo.get("provider_name") or "").strip()
                    if n and n not in names:
                        names.append(n)
                names = names[:8]
                if names:
                    play_from = "$$$".join(names)
                    play_url = "$$$".join([play_url] * len(names))

        content = self._clean(d.get("description") or "")
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        return {"list": [{
            "vod_id": vid,
            "vod_name": self._clean(d.get("title", "")),
            "vod_pic": self._fix_url(d.get("poster_url", "")),
            "vod_year": str(d.get("year") or ""),
            "vod_area": self._clean(d.get("area") or ""),
            "vod_class": "/".join((d.get("genres") or [])[:3]),
            "vod_director": "/".join((d.get("directors") or [])[:2]),
            "vod_actor": "/".join((d.get("actors") or [])[:3]),
            "vod_content": content,
            "vod_remarks": self._clean(d.get("status") or d.get("remarks") or ""),
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }]}

    def searchContent(self, key, quick=False, pg="1"):
        k = str(key or "").strip()
        if not k:
            return {"list": []}

        try:
            pn = max(int(str(pg)), 1)
        except Exception:
            pn = 1

        ck = "q_%s_p%d" % (k, pn)
        now = time.time()
        if (self._sc_t.get(ck, 0) > now - 300) and (ck in self._sc):
            return self._sc[ck]

        path = "/v1/browse/catalog?q=%s&page=%d&limit=20" % (
            urllib.parse.quote(k), pn)
        self.log("search: %s" % path)
        j = self._req("GET", path)
        cards = j.get("cards") or []
        total = (j.get("pagination") or {}).get("total", 0) or 0

        r = {
            "list": [self._vod(c) for c in cards if c],
            "page": pn,
            "pagecount": max(math.ceil(total / 20.0), 1) if total else 1,
            "limit": 20,
            "total": total or len(cards),
        }
        self._sc[ck], self._sc_t[ck] = r, now
        return r

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 播放 ----------------

    def playerContent(self, flag, id, vipFlags=None, vipIds=None):
        tok = str(id or "").strip()
        if not tok:
            return {"url": ""}

        # 如果 id 本身已经是直链，直接返回
        if tok.startswith("http") and (".m3u8" in tok or ".mp4" in tok):
            return {
                "parse": 0, "playUrl": "", "url": tok,
                "header": {"User-Agent": UA, "Referer": self._host() + "/"},
            }

        self.log("player: flag=%s tok=%s" % (flag, tok[:32]))

        # 1) yjm3u8 直链探测
        murl = YJ % tok
        rsp = self._fetch(murl, headers={"User-Agent": UA}, timeout=10)
        if rsp is not None:
            code = getattr(rsp, "status_code", 0)
            text = getattr(rsp, "text", "") or ""
            if code == 200 and "#EXTM3U" in text:
                self.log("  => yjm3u8 直链")
                return {
                    "parse": 0, "playUrl": "", "url": murl,
                    "header": {"User-Agent": UA, "Referer": self._host() + "/"},
                }

        # 2) yjapi JSON
        api_url = YJ_API % tok
        rsp = self._fetch(api_url, headers={
            "User-Agent": UA, "Accept": "application/json",
            "Referer": self._host() + "/",
        }, timeout=10)
        if rsp is not None and getattr(rsp, "status_code", 0) == 200:
            try:
                j = rsp.json()
                u = (j.get("url") or "") if isinstance(j, dict) else ""
                if u:
                    self.log("  => yjapi 直链")
                    return {
                        "parse": 0, "playUrl": "", "url": u,
                        "header": {"User-Agent": UA,
                                   "Referer": self._host() + "/"},
                    }
            except Exception:
                pass

        # 3) resolve -> resolve-line
        j = self._req("GET", "/v1/playback/resolve/%s" % tok)
        lines = j.get("line_options") or []
        wanted = str(flag or "")
        if wanted and wanted != "kanju":
            picked = [l for l in lines
                      if (l.get("provider_name") or "") == wanted]
            lines = picked or lines

        for lo in lines:
            t = lo.get("url") or ""
            if t.startswith("resolve://"):
                t = t[10:]
            if not t:
                continue
            rj = self._req("POST", "/v1/playback/resolve-line", {"ticket": t})
            url = (rj.get("line") or {}).get("url") or ""
            if url:
                self.log("  => resolve-line 直链")
                return {
                    "parse": 0, "playUrl": "", "url": url,
                    "header": {"User-Agent": UA, "Referer": self._host() + "/"},
                }

        # 兜底：交给 TVBox 嗅探
        self.log("  => 兜底 parse=1")
        return {
            "parse": 1, "playUrl": "", "url": "",
            "header": {"User-Agent": UA, "Referer": self._host() + "/"},
        }

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
            rsp = self._fetch(url, headers={
                "User-Agent": UA, "Referer": self._host() + "/"}, timeout=15)
            if rsp is None:
                return [200, "image/jpeg", b"", ""]
            content = getattr(rsp, "content", b"") or b""
            ctype = ""
            try:
                ctype = rsp.headers.get("Content-Type", "") or ""
            except Exception:
                ctype = ""
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        if not url:
            return False
        u = str(url).lower()
        return ".m3u8" in u or ".mp4" in u or u.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
