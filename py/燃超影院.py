# coding=utf-8
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
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[rancho]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.aarnadhya.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "短剧"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "5",  "type_name": "综艺"},
    {"type_id": "48", "type_name": "网飞新剧"},
    {"type_id": "47", "type_name": "AI漫剧"},
]

FILTERS = {c["type_id"]: [] for c in CLASSES}

_RE_CARD = re.compile(
    r'<a\s+href="(/video/[^"]+\.html)"[^>]*?class="zj-item"[^>]*?>([\s\S]*?)</a>',
    re.S | re.I)
_RE_TITLE = re.compile(r'title="([^"]*)"', re.I)
_RE_IMG = re.compile(r'<img[^>]*?src="([^"]*)"', re.I)
_RE_CORNER = re.compile(r'<div\s+class="zj-corner[^"]*"[^>]*title="([^"]*)"', re.I)


class Spider(Spider):

    def getName(self):
        return "燃超影院"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": UA,
            "Referer": HOST + "/",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.log("init done")

    def _fetch(self, url):
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=20)
            return rsp.text or ""
        except Exception as e:
            self.log("fetch fail %s -> %s" % (url, e))
            return ""

    def _extract(self, html):
        out = []
        seen = set()
        for m in _RE_CARD.finditer(html):
            href = m.group(1)
            inner = m.group(2)
            if href in seen:
                continue
            seen.add(href)
            tm = _RE_TITLE.search(m.group(0))
            name = tm.group(1) if tm else ""
            im = _RE_IMG.search(inner)
            pic = im.group(1) if im else ""
            cm = _RE_CORNER.search(inner)
            remark = cm.group(1) if cm else ""
            out.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return out

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(HOST + "/")
        self.log("home html=%d" % len(html))
        return {"list": self._extract(html)}

    def categoryContent(self, tid, pg, filter, extend):
        url = "%s/tv/%s.html" % (HOST, tid)
        self.log("category url=%s" % url)
        html = self._fetch(url)
        self.log("category html=%d" % len(html))
        videos = self._extract(html)
        self.log("category videos=%d" % len(videos))
        return {
            "list": videos, "page": 1, "pagecount": 1,
            "limit": 36, "total": len(videos),
        }

    def searchContent(self, key, quick, pg="1"):
        return {"list": []}

    def detailContent(self, ids):
        return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        return {"parse": 1, "url": id}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
