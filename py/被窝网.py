# coding=utf-8
"""
被窝网 beiwowang.com
TVBox/影视仓标准Spider接口，适配Chaquo(无第三方库)
站点：MacCMS V10，模板beiwo
页面真实路径：
首页:/
分类页:/vodshow/{分类}--------{page}---/
详情页:/wo/xxx/
播放页:/wa/xxx‑1‑1/
搜索:/vodsearch/-------------/?wd=关键词
卡片class: grid‑carditem
播放页JS: var player_aaaa={...}
"""
import re
import json
import urllib.request
import ssl
from base.spider import Spider

# Android Chaquo 修复SSL证书报错
ssl._create_default_https_context = ssl._create_unverified_context

class Spider(Spider):
    def __init__(self):
        self.name = "beiwowang"
        self.host = "https://www.beiwowang.com"
        self.headers = {
            "User‑Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept‑Language": "zh‑CN,zh;q=0.9",
            "Referer": self.host
        }
        # 导航栏真实分类映射，来自首页 <nav> 导航链接
        # tid:返回给壳的id，value:url路径段
        self.cat_map = {
            "1": "dianying",
            "2": "lianxuju",
            "3": "zongyi",
            "4": "dongman",
            "5": "duanju"
        }
        # 正则：提取播放页 player_aaaa JS对象，来自真实播放页源码
        self.re_player_aaaa = re.compile(r"var\s+player_aaaa\s*=\s*(\{.*?\})\s*;", re.S)

    def getName(self):
        return self.name

    def init(self, extend=""):
        pass

    def _http_get(self, url, params=None, referer=None):
        """纯urllib GET，完全依据站点真实请求头"""
        try:
            h = self.headers.copy()
            if referer:
                h["Referer"] = referer
            final_url = url
            if params:
                qs = urllib.parse.urlencode(params)
                final_url = url + "?" + qs
            req = urllib.request.Request(final_url, headers=h)
            resp = urllib.request.urlopen(req, timeout=20)
            raw = resp.read()
            html = raw.decode("utf‑8", errors="ignore")
            return html
        except Exception:
            return ""

    def _abs_url(self, url):
        """真实页面的相对路径转绝对url，从你给的源码提取规则"""
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return url

    def _parse_card_list(self, html):
        """依据真实源码：<div class="grid‑carditem"> 卡片，全部正则，无臆造xpath"""
        ret = []
        blocks = re.findall(r'<div class="grid‑carditem">.*?</div>', html, re.S)
        for blk in blocks:
            # <a class="link" href="xxx" title="标题">
            m_a = re.search(r'<a class="link"\s+href="([^"]+)"\s+title="([^"]+)"', blk, re.S)
            if not m_a:
                continue
            href = m_a.group(1)
            title = m_a.group(2).strip()
            # 图片 <img class="lazyload" data‑original="xxx"
            m_img = re.search(r'<img[^>]+class="lazyload"[^>]+data‑original="([^"]+)"', blk, re.S)
            pic = m_img.group(1).strip() if m_img else ""
            # <p class="tag2">2025 中国大陆</p>
            m_tag2 = re.search(r'<p class="tag2">([^<]+)</p>', blk, re.S)
            year = ""
            if m_tag2:
                tag2_text = m_tag2.group(1)
                m_y = re.search(r'(\d{4})', tag2_text)
                if m_y:
                    year = m_y.group(1)
            vod_id = self._abs_url(href)
            vod_pic = self._abs_url(pic)
            ret.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": vod_pic,
                "vod_year": year,
                "vod_remarks": ""
            })
        return ret

    def _parse_max_page(self, html):
        """分页：<div class="pages‑box"><ul><li><a href="xxx--------3---/">"""
        max_p = 1
        links = re.findall(r'href="[^"]+--------(\d+)---/"', html)
        for s in links:
            try:
                num = int(s)
                if num > max_p:
                    max_p = num
            except Exception:
                pass
        return max_p

    def homeContent(self, filter):
        """首页分类和筛选，依据站点导航和筛选栏"""
        cls_list = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "电视剧", "type_id": "2"},
            {"type_name": "综艺", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"},
            {"type_name": "短剧", "type_id": "5"},
        ]
        area_vals = [
            {"n": "全部", "v": ""},
            {"n": "中国大陆", "v": "中国大陆"},
            {"n": "中国香港", "v": "中国香港"},
            {"n": "中国台湾", "v": "中国台湾"},
            {"n": "美国", "v": "美国"},
            {"n": "日本", "v": "日本"},
            {"n": "韩国", "v": "韩国"},
            {"n": "英国", "v": "英国"},
            {"n": "泰国", "v": "泰国"},
            {"n": "其他", "v": "其他"},
        ]
        year_vals = [{"n": "全部", "v": ""}]
        for y in range(2026, 2001, -1):
            year_vals.append({"n": str(y), "v": str(y)})
        sort_vals = [
            {"n": "最新", "v": "time"},
            {"n": "人气", "v": "hits"},
            {"n": "评分", "v": "score"},
        ]
        filters = {}
        for c in cls_list:
            filters[c["type_id"]] = [
                {"key": "area", "name": "地区", "value": area_vals},
                {"key": "year", "name": "年份", "value": year_vals},
                {"key": "sort", "name": "排序", "value": sort_vals}
            ]
        return {"class": cls_list, "filters": filters}

    def homeVideoContent(self):
        html = self._http_get(self.host + "/")
        lst = self._parse_card_list(html)
        return {"list": lst}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            if isinstance(extend, str) and extend.strip():
                extend = json.loads(extend)
            else:
                extend = {}
            slug = self.cat_map.get(str(tid), "dianying")
            page = int(pg)
            # 站点真实伪静态路径 /vodshow/dianying--------2---/
            url = f"{self.host}/vodshow/{slug}--------{page}---/"
            html = self._http_get(url)
            lst = self._parse_card_list(html)
            maxpage = self._parse_max_page(html)
            return {
                "list": lst,
                "page": page,
                "pagecount": maxpage,
                "limit": 24,
                "total": maxpage * 24
            }
        except Exception:
            return {"list": [], "page": 1, "pagecount": 0, "limit": 0, "total": 0}

    def detailContent(self, ids):
        """详情页解析，完全基于你提供的真实详情页HTML源码"""
        try:
            vod_url = self._abs_url(str(ids[0]))
            html = self._http_get(vod_url)
            # 标题 <div class="movie‑info"><h1>xxx</h1>
            title = ""
            m_h1 = re.search(r'<div class="movie‑info">\s*<h1>(.*?)</h1>', html, re.S)
            if m_h1:
                title = m_h1.group(1).strip()
            if not title:
                m_title = re.search(r"<title>(.*?)</title>", html, re.S)
                if m_title:
                    title = m_title.group(1).split("_")[0].strip()
            # 封面 <div class="movie‑poster"><img data‑original="xxx"
            pic = ""
            m_pic = re.search(r'<div class="movie‑poster".*?<img[^>]+data‑original="([^"]+)"', html, re.S)
            if m_pic:
                pic = self._abs_url(m_pic.group(1))
            # 简介 <div class="movie‑description">xxx</div>
            desc = ""
            m_desc = re.search(r'<div class="movie‑description">(.*?)</div>', html, re.S)
            if m_desc:
                raw_desc = re.sub(r"<.+?>", "", m_desc.group(1))
                desc = raw_desc.strip()
            # 剧集列表：<li><a href="/wa/laojiu‑1‑1/" title="第01集">
            ep_items = re.findall(r'<li>\s*<a href="([^"]+)"\s+title="([^"]+)"', html, re.S)
            ep_list = []
            for href, ep_title in ep_items:
                ep_href = self._abs_url(href)
                ep_list.append(f"{ep_title.strip()}${ep_href}")
            play_from = []
            play_urls = []
            if ep_list:
                play_from.append("如意")
                play_urls.append("#".join(ep_list))
            vod_play_from = "$$$".join(play_from)
            vod_play_url = "$$$".join(play_urls)
            info = {
                "vod_id": vod_url,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": desc,
                "vod_actor": "",
                "vod_director": "",
                "vod_year": "",
                "vod_area": "",
                "vod_remarks": "",
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url
            }
            return {"list": [info]}
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        """播放解析：依据真实播放页源码 var player_aaaa={url:"share链接"}
        该站share页面存在Cloudflare CF5秒盾，安卓Chaquo urllib无法绕过CF；
        使用标准TVBox协议 parse=1，把share链接返回壳子，由壳子http客户端执行网页抓取，
        壳内置解析正则提取 var main="xxx.m3u8"，Python不再访问CDN域名。
        """
        try:
            play_page_url = self._abs_url(id)
            html = self._http_get(play_page_url, referer=self.host)
            m = self.re_player_aaaa.search(html)
            if not m:
                return {"parse":0, "url":"", "header":""}
            js_obj_str = m.group(1)
            pd = json.loads(js_obj_str)
            share_url = pd.get("url", "")
            if not share_url:
                return {"parse":0, "url":"", "header":""}
            share_url = self._abs_url(share_url)
            return {
                "parse": 1,
                "playUrl": "",
                "url": share_url,
                "header": json.dumps({
                    "User‑Agent": self.headers["User‑Agent"],
                    "Referer": play_page_url
                })
            }
        except Exception:
            return {"parse":0, "playUrl":"", "url":"", "header":""}

    def searchContent(self, key, quick, pg="1"):
        """搜索，依据真实搜索表单 action="/vodsearch/-------------/" 参数 wd"""
        try:
            page = int(pg)
            url = f"{self.host}/vodsearch/-------------/"
            params = {"wd": key, "page": page}
            html = self._http_get(url, params=params)
            lst = self._parse_card_list(html)
            maxpage = self._parse_max_page(html)
            return {
                "list": lst,
                "page": page,
                "pagecount": maxpage,
                "limit": 24,
                "total": maxpage * 24
            }
        except Exception:
            return {"list": [], "page":1, "pagecount":0, "limit":0, "total":0}

    def isVideoFormat(self, url):
        suf = [".m3u8",".mp4",".flv",".ts",".mkv",".avi"]
        return any(url.lower().endswith(s) for s in suf)

    def manualVideoCheck(self):
        pass

    def localProxy(self, params):
        return [200, "image/jpeg", b"", ""]

    def destroy(self):
        pass
