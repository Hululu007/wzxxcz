# -*- coding: utf-8 -*-
"""
==============================================
 小橙子影视 - 323433ssdfd.top (多多追剧) TVBox 爬虫 
==============================================
 说明:
   - 站点为 Vue SPA (多多影视), 数据走 /api.php/web/* JSON 接口
   - 需要携带 X-Client / web-sign 鉴权请求头
   - 播放链接为 wasm 加密的 decode/url 接口, 无法纯 Python 复原签名,
     故 playerContent 返回 SPA 播放页, 由 TVBox webview 嗅探 m3u8 (parse:1)
==============================================
"""
import sys
import json
import re
import time
import urllib.parse
import urllib.request

sys.path.append(__file__)

# ================= 站点配置 =================
SITE_HOST = "https://323433ssdfd.top"
SITE_NAME = "小橙子影视"
UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
TIMEOUT = 15

# 鉴权请求头 (从前端 index.js 提取)
X_CLIENT = "8f3d2a1c7b6e5d4c9a0b1f2e3d4c5b6a"
WEB_SIGN = "ddtvf65f3a83d6d9ad6f"

# 简介前缀
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 分类 (与站点 categories 保持一致)
CATE_LIST = [("1", "电影"), ("2", "剧集"), ("3", "动漫"), ("4", "综艺")]

# 筛选条件
FILTER_CLASSES = {
    "1": ["全部", "动作", "喜剧", "爱情", "科幻", "恐怖", "剧情", "战争", "犯罪", "武侠"],
    "2": ["全部", "古装", "都市", "悬疑", "家庭", "年代", "谍战", "奇幻"],
    "3": ["全部", "国产动漫", "日韩动漫", "欧美动漫", "奇幻", "冒险"],
    "4": ["全部", "真人秀", "脱口秀", "访谈", "选秀"],
}
FILTER_AREAS = ["全部", "中国大陆", "中国香港", "中国台湾", "美国", "韩国", "日本", "泰国", "英国"]
FILTER_YEARS = ["全部", "2026", "2025", "2024", "2023", "2022", "2021", "2020", "更早"]
FILTER_SORTS = [("最新", ""), ("最热", "hits"), ("评分", "score")]


def log(*args):
    try:
        print("[%s]" % SITE_NAME, *args)
    except Exception:
        pass


class Spider(object):

    def init(self, extend=""):
        log("init extend=", extend)
        return ""

    # ---------------- 基础请求 ----------------
    def _headers(self, extra=None):
        h = {
            "User-Agent": UA,
            "Referer": SITE_HOST + "/",
            "Origin": SITE_HOST,
            "Accept": "application/json",
            "X-Client": X_CLIENT,
            "web-sign": WEB_SIGN,
        }
        if extra:
            h.update(extra)
        return h

    def _get(self, path, params=None):
        url = SITE_HOST + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers=self._headers())
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:
            log("GET fail:", path, e)
            return None

    def _post(self, path, params=None, body=None):
        url = SITE_HOST + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body or {}, ensure_ascii=False).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=data, method="POST",
                                         headers=self._headers({"Content-Type": "application/json"}))
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:
            log("POST fail:", path, e)
            return None

    # ---------------- 解析辅助 ----------------
    @staticmethod
    def _clean(text):
        """清理简介中的 HTML 标签与转义"""
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", "", str(text))
        text = text.replace("&nbsp;", " ").replace("&amp;", "&")
        text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _fix_url(pic):
        """补全图片协议"""
        if not pic:
            return ""
        pic = str(pic).strip()
        if pic.startswith("//"):
            return "https:" + pic
        return pic

    def _to_video(self, item):
        """接口视频对象 -> TVBox 标准结构"""
        return {
            "vod_id": str(item.get("vod_id", "")),
            "vod_name": str(item.get("vod_name", "")).strip(),
            "vod_pic": self._fix_url(item.get("vod_pic", "")),
            "vod_remarks": str(item.get("vod_remarks", "")).strip(),
        }

    def _safe(self, d):
        """防御式取接口 data 列表"""
        if not isinstance(d, dict):
            return []
        data = d.get("data")
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        return []

    # ---------------- TVBox 入口 ----------------
    def homeContent(self, filter):
        result = {"class": [], "filters": {}}
        for tid, name in CATE_LIST:
            result["class"].append({"type_id": tid, "type_name": name})
            cls = [{"n": "全部", "v": ""}] + [{"n": c, "v": c} for c in FILTER_CLASSES.get(tid, []) if c != "全部"]
            result["filters"][tid] = [
                {"key": "class", "name": "类型", "value": cls},
                {"key": "area", "name": "地区", "value":
                    [{"n": a, "v": a if a != "全部" else ""} for a in FILTER_AREAS]},
                {"key": "year", "name": "年份", "value":
                    [{"n": y, "v": y if y != "全部" else ""} for y in FILTER_YEARS]},
                {"key": "sort", "name": "排序", "value":
                    [{"n": n, "v": v} for n, v in FILTER_SORTS]},
            ]
        return result

    def homeVideoContent(self):
        videos = []
        try:
            d = self._get("/api.php/web/index/home")
            data = d.get("data") if isinstance(d, dict) else {}
            if not isinstance(data, dict):
                data = {}
            seen = set()
            for block in data.get("categories", []) or []:
                for v in block.get("videos", []) or []:
                    vid = str(v.get("vod_id", ""))
                    if vid and vid not in seen:
                        seen.add(vid)
                        videos.append(self._to_video(v))
            # 推荐/热榜补位
            for v in data.get("recommend", []) or []:
                vid = str(v.get("vod_id", ""))
                if vid and vid not in seen and len(videos) < 60:
                    seen.add(vid)
                    videos.append(self._to_video(v))
        except Exception as e:
            log("homeVideo err:", e)
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend or {}
        body = {
            "type_name": "",
            "type_id": str(tid),
            "page": int(pg) if str(pg).isdigit() else 1,
            "sort": extend.get("sort", "") or "",
            "class": extend.get("class", "") or "",
            "area": extend.get("area", "") or "",
            "year": extend.get("year", "") or "",
        }
        videos, pagecount, total = [], 1, 0
        try:
            d = self._post("/api.php/web/filter/vod", body=body)
            items = self._safe(d)
            videos = [self._to_video(v) for v in items]
            total = int(d.get("total") or 0) if isinstance(d, dict) else 0
            pagecount = int(d.get("pageCount") or 1) if isinstance(d, dict) else 1
            limit = int(d.get("limit") or 24) if isinstance(d, dict) else 24
            # 接口 total 固定返回单页数量, 用满页特征判断还有下一页
            if len(items) >= limit:
                pagecount = max(pagecount, body["page"] + 1)
        except Exception as e:
            log("category err:", e)
        result = {
            "list": videos,
            "page": body["page"],
            "pagecount": pagecount,
            "limit": 24,
            "total": max(total, len(videos)),
        }
        return result

    def detailContent(self, ids):
        tid = ids[0] if isinstance(ids, list) else ids
        vod = {}
        try:
            d = self._get("/api.php/web/vod/get_detail", {"vod_id": tid})
            items = self._safe(d)
            if items:
                info = items[0]
                vod = self._to_video(info)
                vod["type_name"] = self._clean(info.get("vod_class", ""))
                vod["vod_year"] = self._clean(info.get("vod_year", ""))
                vod["vod_area"] = self._clean(info.get("vod_area", ""))
                vod["vod_lang"] = self._clean(info.get("vod_lang", ""))
                vod["vod_actor"] = self._clean(info.get("vod_actor", ""))
                vod["vod_director"] = self._clean(info.get("vod_director", ""))
                intro = self._clean(info.get("vod_content", ""))
                vod["vod_content"] = (INTRO_PREFIX + "\n" + intro) if intro else INTRO_PREFIX
                # 播放源: from 用 $$$ 分隔, url 同序, 每集为 名称$token
                play_from = str(info.get("vod_play_from", ""))
                play_url = str(info.get("vod_play_url", ""))
                names = [x.strip() for x in play_from.split("$$$") if x.strip()]
                groups = play_url.split("$$$")
                vod_play_from, vod_play_url = [], []
                for i, name in enumerate(names):
                    eps = []
                    if i < len(groups):
                        for ep in groups[i].split("#"):
                            if "$" in ep:
                                en, et = ep.split("$", 1)
                                # 集数 id 编码为 vod_id|token, 供 playerContent 取 vod_id
                                eps.append(self._clean(en) + "$" + str(tid) + "|" + et.strip())
                            elif ep.strip():
                                eps.append(ep.strip())
                    if eps:
                        vod_play_from.append(name)
                        vod_play_url.append("#".join(eps))
                vod["vod_play_from"] = "$$$".join(vod_play_from)
                vod["vod_play_url"] = "$$$".join(vod_play_url)
        except Exception as e:
            log("detail err:", e)
        if not vod:
            vod = {"vod_id": str(tid), "vod_name": "", "vod_content": INTRO_PREFIX}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1
        videos, pagecount = [], 1
        try:
            d = self._get("/api.php/web/search/index", {"wd": key, "page": pg})
            videos = [self._to_video(v) for v in self._safe(d)]
            if isinstance(d, dict):
                try:
                    pagecount = max(1, int(d.get("pageCount") or 1))
                except Exception:
                    pagecount = 1
        except Exception as e:
            log("search err:", e)
        return {"list": videos, "page": pg, "pagecount": pagecount,
                "limit": 15, "total": len(videos)}

    def playerContent(self, flag, id, vipFlags):
        """
        播放接口的 token 由 wasm 加密解码, 无法纯 Python 复原签名,
        这里返回 SPA 播放页交给 TVBox webview 嗅探 m3u8 (parse:1)
        集数 id 格式: "<vod_id>|<token>"
        """
        vod_id = str(id).split("|")[0]
        play_url = SITE_HOST + "/play/" + vod_id
        res = {
            "parse": 1,
            "playUrl": "",
            "url": play_url,
            "header": {
                "User-Agent": UA,
                "Referer": SITE_HOST + "/",
            },
        }
        log("player:", flag, "->", play_url)
        return res

    def isVideoFormat(self, url):
        return False

    def regVideoFormat(self, url):
        return False

    def localProxy(self, params):
        return [200, "text/plain", "", ""]


# ---------------- 本地调试 ----------------
if __name__ == "__main__":
    sp = Spider()
    sp.init()
    print("--- home ---")
    print(json.dumps(sp.homeContent(1), ensure_ascii=False)[:400])
    print("--- homeVideo ---")
    hv = sp.homeVideoContent()
    print(json.dumps(hv["list"][:3], ensure_ascii=False))
    print("--- category 1 p1 ---")
    c = sp.categoryContent("1", "1", 1, {})
    print(json.dumps(c["list"][:3], ensure_ascii=False))
    vid = c["list"][0]["vod_id"] if c["list"] else "159887"
    print("--- detail %s ---" % vid)
    dt = sp.detailContent([vid])
    v = dt["list"][0]
    print(v["vod_name"], "|", v["vod_play_from"])
    print("intro:", v["vod_content"][:80])
    print("play_url head:", v["vod_play_url"][:100])
    print("--- search 凡人 ---")
    s = sp.searchContent("凡人", "0", "1")
    print(json.dumps(s["list"][:2], ensure_ascii=False))
    print("--- player ---")
    ep = v["vod_play_url"].split("#")[0].split("$", 1)[1] if v.get("vod_play_url") else ""
    print(json.dumps(sp.playerContent(v["vod_play_from"].split("$$$")[0], ep, ""), ensure_ascii=False))
