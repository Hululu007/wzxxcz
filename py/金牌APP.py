# coding=utf-8
"""
蓝兔子影院 www.lwdys.com | TVBox Python 爬虫 
关键:
  - 全站走 /mw-movie/anonymous 接口, 服务端签名 sign = SHA1(MD5(排序参数 + key + t))
  - 分类 /anonymous/video/list, 搜索 /anonymous/video/searchByWord
  - 详情 /anonymous/video/detail (含 episodeList)
  - 播放 /anonymous/v2/video/episode/url -> 直链 m3u8 (parse=0)
"""
import re
import sys
import json
import time
import hashlib
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
                print("[lwdys]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.lwdys.com"
API = HOST + "/mw-movie/anonymous"

# 从前端 JS (chunk 2844) 逆向得到的固定 signKey
SIGN_KEY = "cb808529bae6b6be45ecfab29a4889bc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "88", "type_name": "短剧"},
]

_SORTS = [{"n": "综合排序", "v": ""},
          {"n": "豆瓣评分", "v": "douban"},
          {"n": "热度最高", "v": "hot"},
          {"n": "最新上架", "v": "new"}]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "中国大陆", "v": "中国大陆"}, {"n": "美国", "v": "美国"},
    {"n": "中国香港", "v": "中国香港"}, {"n": "中国台湾", "v": "中国台湾"},
    {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"},
    {"n": "英国", "v": "英国"}, {"n": "法国", "v": "法国"},
    {"n": "泰国", "v": "泰国"}, {"n": "印度", "v": "印度"},
    {"n": "其它", "v": "其它"},
]

_FILTERS_MAP = {
    "1": ["全部", "剧情", "喜剧", "动作", "爱情", "惊悚", "犯罪", "恐怖",
          "悬疑", "冒险", "奇幻", "科幻", "家庭", "历史", "战争", "纪录片",
          "古装", "音乐", "动画", "传记", "武侠", "运动", "西部", "灾难", "歌舞"],
    "2": ["全部", "剧情", "喜剧", "爱情", "犯罪", "悬疑", "家庭", "古装",
          "惊悚", "动作", "奇幻", "科幻", "都市", "历史", "战争", "冒险",
          "武侠", "恐怖", "青春", "传记", "谍战", "情感", "军旅", "甜宠"],
    "3": ["全部", "真人秀", "脱口秀", "国产综艺", "喜剧", "晚会", "音乐",
          "纪录", "游戏", "生活", "港台综艺", "日韩综艺", "欧美综艺", "美食", "竞技"],
    "4": ["全部", "动画", "冒险", "喜剧", "奇幻", "剧情", "科幻", "动作",
          "儿童", "悬疑", "都市", "家庭", "国漫", "日常", "爱情", "玄幻",
          "日漫", "治愈", "古风", "武侠", "运动", "校园"],
    "88": ["全部", "短剧", "剧情", "爱情", "爽文", "古装", "悬疑", "喜剧",
           "奇幻", "都市", "玄幻", "家庭", "穿越", "武侠", "科幻"],
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


class Spider(Spider):

    def getName(self):
        return "蓝兔子影院"

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
            "Origin": self.site_url,
        }
        self.default_pic = "https://obs.3688baihuo.com/upload/vod_default.webp"
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ===================== 签名 =====================
    def _sign(self, params):
        """sign = SHA1( MD5( 排序参数串 + '&key=..&t=..' ) )"""
        t = str(int(time.time() * 1000))
        ps = {k: str(v) for k, v in params.items()
              if v is not None and str(v) != ""}
        h = "&".join("%s=%s" % (k, ps[k]) for k in sorted(ps))
        h += "&key=%s&t=%s" % (SIGN_KEY, t)
        sign = hashlib.sha1(
            hashlib.md5(h.encode("utf-8")).hexdigest().encode("utf-8")
        ).hexdigest()
        return ps, t, sign

    def _api_get(self, path, params=None, timeout=15):
        try:
            ps, t, sign = self._sign(params or {})
            headers = dict(self.headers)
            headers.update({
                "sign": sign,
                "t": t,
                "authorization": "",
                "deviceId": "web-" + "0" * 16,
            })
            url = API + path
            if ps:
                url += "?" + urllib.parse.urlencode(ps)
            rsp = self.fetch(url, headers=headers, timeout=timeout)
            text = rsp.text if hasattr(rsp, "text") else str(rsp)
            try:
                data = json.loads(text)
            except Exception:
                self.log("api %s 非 JSON: %s" % (path, text[:120]))
                return None
            if data.get("code") != 200:
                self.log("api %s code=%s msg=%s" %
                         (path, data.get("code"), data.get("msg")))
                return None
            return data.get("data")
        except Exception as e:
            self.log("api %s FAIL: %s" % (path, e))
            return None

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

    # ===================== 列表通用 =====================
    def _video_to_item(self, it):
        pic = it.get("vodPic") or self.default_pic
        name = self._clean(it.get("vodName") or "")[:100]
        remark = it.get("vodRemarks") or ""
        if not remark and it.get("vodScore"):
            remark = "%.1f分" % it["vodScore"] if isinstance(
                it.get("vodScore"), float) else str(it.get("vodScore"))
        return {
            "vod_id": str(it.get("vodId", "")),
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": str(remark)[:20],
        }

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        # 用电影分类首页第一页作为推荐位
        data = self._api_get("/video/list",
                             {"type1": 1, "pageNum": 1, "pageSize": 24})
        videos = []
        if data and data.get("list"):
            videos = [self._video_to_item(x) for x in data["list"]]
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        params = {
            "type1": tid,
            "pageNum": page,
            "pageSize": 24,
        }
        if extend.get("class"):
            params["class"] = extend["class"]
        if extend.get("year"):
            params["year"] = extend["year"]
        if extend.get("area"):
            params["area"] = extend["area"]

        data = self._api_get("/video/list", params)
        videos = []
        pagecount = 1
        total = 0
        if data and data.get("list"):
            videos = [self._video_to_item(x) for x in data["list"]]
            try:
                pagecount = int(data.get("totalPage") or 1)
                total = int(data.get("totalCount") or 0)
            except Exception:
                pass
        self.log("category %s page=%d -> %d 条" % (tid, page, len(videos)))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": total,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        data = self._api_get("/video/searchByWord", {
            "keyword": key, "pageNum": page, "pageSize": 20,
        })
        videos = []
        pagecount = 1
        total = 0
        if data:
            res = data.get("result") or {}
            if res.get("list"):
                videos = [self._video_to_item(x) for x in res["list"]]
            try:
                pagecount = int(res.get("totalPage") or 1)
                total = int(res.get("totalCount") or 0)
            except Exception:
                pass
        self.log("search '%s' page=%d -> %d 条" % (key, page, len(videos)))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 20, "total": total,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ===================== 详情 =====================
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        data = self._api_get("/video/detail", {"id": vod_id})
        if not data:
            return {"list": []}

        name = self._clean(data.get("vodName") or "") or vod_id
        pic = data.get("vodPic") or self.default_pic

        content = self._clean(data.get("vodContent") or "") \
            or self._clean(data.get("vodBlurb") or "")
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        actor = self._clean(data.get("vodActor") or "")
        actor = re.sub(r",\s*", ", ", actor)
        director = self._clean(data.get("vodDirector") or "")

        score = ""
        try:
            if data.get("vodDoubanScore"):
                score = str(data["vodDoubanScore"])
            elif data.get("vodScore"):
                score = str(data["vodScore"])
        except Exception:
            pass

        remarks = self._clean(data.get("vodRemarks") or "")
        year = data.get("vodYear") or ""
        area = data.get("vodArea") or ""
        vclass = data.get("vodClass") or ""
        pubdate = data.get("vodPubdate") or ""
        hits = data.get("vodHits") or 0
        lang = data.get("vodLang") or ""

        # 剧集 (episodeList: nid + name), id 编码为 "vodId-nid"
        eps = data.get("episodeList") or []
        eps = sorted(eps, key=lambda e: e.get("sort") or 0)
        play_url = "#".join(
            "%s$%s-%s" % (self._clean(e.get("name") or ("第%d集" % (i + 1))),
                          vod_id, e.get("nid"))
            for i, e in enumerate(eps) if e.get("nid"))

        info = []
        if year:
            info.append("年份：" + str(year))
        if area:
            info.append("地区：" + str(area))
        if vclass:
            info.append("类型：" + str(vclass))
        if lang:
            info.append("语言：" + str(lang))
        if pubdate:
            info.append("上映：" + str(pubdate))
        if hits:
            info.append("热度：%s" % hits)
        info_txt = "\n".join(info)

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": info_txt + "\n\n" + content if info_txt else content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remarks or ("共%d集" % len(eps) if eps else ""),
            "vod_play_from": "蓝兔子专线",
            "vod_play_url": play_url,
        }]}

    # ===================== 播放 =====================
    def playerContent(self, flag, id, vipFlags):
        # id 格式: "vodId-nid" (兼容仅传 nid 的情况)
        if "-" in str(id):
            vod_id, nid = str(id).split("-", 1)
        else:
            vod_id, nid = "0", str(id)
        self.log("player: vod=%s nid=%s flag=%s" % (vod_id, nid, flag))

        cache_key = str(id)
        now = int(time.time())
        if cache_key in self._play_cache:
            ts, res = self._play_cache[cache_key]
            if now - ts < 600:
                return res

        # clientType=1 (Web)。返回按清晰度排列的直链列表
        data = self._api_get("/v2/video/episode/url", {
            "id": vod_id,
            "nid": nid,
            "clientType": 1,
        })

        url = ""
        if data and data.get("list"):
            # 优先 1080, 其次按顺序取第一个
            best = None
            for it in data["list"]:
                u = it.get("url") or ""
                if not u:
                    continue
                if it.get("needLogin"):
                    continue
                if ".m3u8" not in u.lower() and ".mp4" not in u.lower():
                    continue
                if best is None or (it.get("resolution") or 0) > \
                        (best.get("resolution") or 0):
                    best = it
            if best is None:
                for it in data["list"]:
                    u = it.get("url") or ""
                    if u:
                        best = it
                        break
            if best:
                url = best["url"]
                self.log("  => %sP: %s" %
                         (best.get("resolution", "?"), url[:120]))

        if url:
            res = {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
        else:
            # 兜底: 交给嗅探
            res = {
                "parse": 1,
                "playUrl": "",
                "url": "%s/vod/play/0/sid/%s" % (self.site_url, nid),
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
        self._play_cache[cache_key] = (now, res)
        return res

    def localProxy(self, param):
        return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
