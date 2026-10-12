# coding=utf-8
"""
被窝网 beiwowang.com
适配 webhtv Chaquo 壳【纯标准库版本，无requests、无lxml】
TVBOX/影视仓协议，playerContent内部完整解析，parse=0，不需要修改Java壳
仅用于本地技术学习，版权风险自行承担
"""
import re
import json
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from base.spider import Spider

# 简易HTML解析器，替代lxml，纯标准库
class SimpleHtmlParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.card_list = []
        self.current_card = None
        self.in_card = False

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        cls = attr_dict.get("class", "")
        if tag == "div" and "grid-carditem" in cls:
            self.in_card = True
            self.current_card = {"title": "", "href": "", "img": "", "tag1": "", "tag2": ""}
        if self.in_card and tag == "a" and "link" in cls:
            self.current_card["href"] = attr_dict.get("href", "")
            self.current_card["title"] = attr_dict.get("title", "")
        if self.in_card and tag == "img" and "lazyload" in cls:
            self.current_card["img"] = attr_dict.get("data-original", "") or attr_dict.get("src", "")

    def handle_data(self, data):
        if self.in_card:
            data = data.strip()
            if not data:
                return
            if len(data) < 30:
                if self.current_card["tag1"] == "":
                    self.current_card["tag1"] = data
                elif self.current_card["tag2"] == "":
                    self.current_card["tag2"] = data

    def handle_endtag(self, tag):
        if tag == "div" and self.in_card:
            self.in_card = False
            if self.current_card:
                self.card_list.append(self.current_card)
                self.current_card = None

class Spider(Spider):
    def __init__(self):
        self.name = "被窝网"
        self.host = "https://www.beiwowang.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.host
        }
        self.RE_PLAYER_AAAA = re.compile(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*;', re.S | re.I)
        self.RE_MAIN = re.compile(r'var\s+main\s*=\s*"([^"]+)"', re.S | re.I)
        self._cat_map = {
            "1": "dianying",
            "2": "lianxuju",
            "3": "zongyi",
            "4": "dongman",
            "5": "duanju",
        }

    def getName(self):
        return self.name

    def init(self, extend=''):
        pass

    # ========== 纯urllib GET请求，替代requests ==========
    def _get(self, url, params=None, referer=None):
        try:
            headers = self.headers.copy()
            if referer:
                headers["Referer"] = referer
            if params:
                query = urllib.parse.urlencode(params)
                url = url + "?" + query
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                html = raw.decode("utf-8", errors="ignore")
            return html
        except Exception:
            return ""

    def _fix_url(self, url):
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        return url

    # ========== 用内置HTMLParser解析列表卡片，替代lxml ==========
    def _parse_video_list(self, html):
        videos = []
        parser = SimpleHtmlParser()
        try:
            parser.feed(html)
        except Exception:
            return []
        for item in parser.card_list:
            vod_id = self._fix_url(item["href"])
            title = item["title"].strip()
            vod_pic = self._fix_url(item["img"])
            vod_remarks = item["tag1"]
            tag2_txt = item["tag2"]
            vod_year = ""
            m_year = re.search(r'(\d{4})', tag2_txt)
            if m_year:
                vod_year = m_year.group(1)
            if not title:
                continue
            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
                "vod_year": vod_year
            })
        return videos

    def _parse_pagecount(self, html):
        total = 1
        links = re.findall(r'href="([^"]+--------\d+---/)', html)
        for link in links:
            m = re.search(r'--------(\d+)---/', link)
            if m:
                p = int(m.group(1))
                if p > total:
                    total = p
        return total

    # ========== 首页分类 ==========
    def homeContent(self, filter):
        classes = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "电视剧", "type_id": "2"},
            {"type_name": "综艺", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"},
            {"type_name": "短剧", "type_id": "5"},
        ]
        area_vals = [{"n": "全部", "v": ""},
            {"n": "中国大陆", "v": "中国大陆"},
            {"n": "中国香港", "v": "中国香港"},
            {"n": "中国台湾", "v": "中国台湾"},
            {"n": "美国", "v": "美国"},
            {"n": "日本", "v": "日本"},
            {"n": "韩国", "v": "韩国"},
            {"n": "英国", "v": "英国"},
            {"n": "法国", "v": "法国"},
            {"n": "泰国", "v": "泰国"},
            {"n": "其他", "v": "其他"},
        ]
        year_vals = [{"n": "全部", "v": ""}]
        for y in range(2026, 2002, -1):
            year_vals.append({"n": str(y), "v": str(y)})
        order_vals = [{"n": "最新", "v": "time"},{"n": "人气", "v": "hits"},{"n": "评分", "v": "score"}]
        filters = {}
        for c in classes:
            filters[c['type_id']] = [
                {"key": "area", "name": "地区", "value": area_vals},
                {"key": "year", "name": "年份", "value": year_vals},
                {"key": "sort", "name": "排序", "value": order_vals},
            ]
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        videos = []
        try:
            html = self._get(self.host + "/")
            videos = self._parse_video_list(html)
        except Exception:
            pass
        return {"list": videos}

    # ========== 分类内容 ==========
    def categoryContent(self, tid, pg, filter, extend):
        videos = []
        try:
            if isinstance(extend, str) and extend:
                extend = json.loads(extend)
            elif not extend:
                extend = {}
            cat_en = self._cat_map.get(str(tid), "dianying")
            area = extend.get("area", "")
            year = extend.get("year", "")
            sort = extend.get("sort", "time")
            page = int(pg)
            url_path = f"{cat_en}--------{page}---/"
            url = f"{self.host}/vodshow/{url_path}"
            params = {}
            if area: params["area"] = area
            if year: params["year"] = year
            if sort and sort != "time": params["order"] = sort
            html = self._get(url, params=params)
            videos = self._parse_video_list(html)
            pc = self._parse_pagecount(html)
            return {'list': videos, 'page': page, 'pagecount': pc, 'limit': 24, 'total': pc * 24}
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 0, 'limit': 0, 'total': 0}

    # ========== 详情页，纯正则提取，不依赖lxml ==========
    def detailContent(self, ids):
        try:
            vod_id = str(ids[0])
            detail_url = self._fix_url(vod_id)
            html = self._get(detail_url)

            # 标题
            vod_name = ""
            h1_match = re.search(r'<div class="movie-info">\s*<h1>(.*?)</h1>', html, re.S)
            if h1_match:
                vod_name = h1_match.group(1).strip()
            if not vod_name:
                title_match = re.search(r'<title>(.*?)</title>', html, re.S)
                if title_match:
                    vod_name = title_match.group(1).split("_")[0].strip()

            # 封面
            vod_pic = ""
            pic_match = re.search(r'<div class="movie-poster".*?<img.*?data-original="([^"]+)"', html, re.S)
            if pic_match:
                vod_pic = pic_match.group(1)
            vod_pic = self._fix_url(vod_pic)

            # 年份
            vod_year = ""
            m_year = re.search(r'(\d{4})', html)
            if m_year:
                vod_year = m_year.group(1)

            # 简介
            vod_content = ""
            desc_match = re.search(r'<div class="movie-description">(.*?)</div>', html, re.S)
            if desc_match:
                vod_content = re.sub(r'<.+?>', "", desc_match.group(1)).strip()

            # 剧集列表
            ep_list = []
            ep_items = re.findall(r'<li>\s*<a href="([^"]+)" title="([^"]+)"', html, re.S)
            for href, title in ep_items:
                ep_href = self._fix_url(href)
                ep_title = title.strip()
                ep_list.append(f"{ep_title}${ep_href}")

            play_from = []
            play_urls = []
            if ep_list:
                play_from.append("如意")
                play_urls.append("#".join(ep_list))

            vod_play_from_str = "$$$".join(play_from)
            vod_play_url_str = "$$$".join(play_urls)

            info = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_content": vod_content,
                "vod_actor": "",
                "vod_director": "",
                "vod_year": vod_year,
                "vod_area": "",
                "vod_remarks": "",
                "vod_play_from": vod_play_from_str,
                "vod_play_url": vod_play_url_str,
            }
            return {"list": [info]}
        except Exception:
            return {"list": []}

    # ========== 播放解析【重点，纯标准库，无第三方包】 ==========
    def playerContent(self, flag, id, vipFlags):
        try:
            play_page_url = self._fix_url(id)
            # 1 获取播放页，拿到player_aaaa
            play_html = self._get(play_page_url, referer=self.host)
            match_player = self.RE_PLAYER_AAAA.search(play_html)
            if not match_player:
                return {"parse":0, "url":"", "header":""}
            player_json_str = match_player.group(1)
            player_data = json.loads(player_json_str)
            share_url = player_data.get("url", "")
            if not share_url:
                return {"parse":0, "url":"", "header":""}
            share_url = self._fix_url(share_url)

            # 2 获取share中转页面，提取var main
            share_html = self._get(share_url, referer=play_page_url)
            match_main = self.RE_MAIN.search(share_html)
            if not match_main:
                return {"parse":0, "url":"", "header":""}
            main_path = match_main.group(1)

            # 拼接m3u8完整地址
            if main_path.startswith("/"):
                url_parse = urllib.parse.urlparse(share_url)
                base_domain = f"{url_parse.scheme}://{url_parse.netloc}"
                real_m3u8 = base_domain + main_path
            else:
                real_m3u8 = main_path

            # 返回结果，壳直接播放，携带防盗链头
            return {
                "parse": 0,
                "playUrl": "",
                "url": real_m3u8,
                "header": json.dumps({
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": share_url
                })
            }
        except Exception:
            return {"parse": 0, "playUrl": "", "url": "", "header": ""}

    # ========== 搜索 ==========
    def searchContent(self, key, quick, pg='1'):
        videos = []
        try:
            page = int(pg)
            search_url = f"{self.host}/vodsearch/-------------/"
            params = {"wd": key, "page": page}
            html = self._get(search_url, params=params)
            videos = self._parse_video_list(html)
            pc = self._parse_pagecount(html)
            return {'list': videos, 'page': page, 'pagecount': pc, 'limit': 24, 'total': pc * 24}
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 0, 'limit': 0, 'total': 0}

    # ========== 壳强制需要的固定方法，不能删 ==========
    def isVideoFormat(self, url):
        return any(url.lower().endswith(fmt) for fmt in ['.m3u8', '.mp4', '.flv', '.ts', '.mkv', '.avi', '.mov'])

    def manualVideoCheck(self):
        pass

    def localProxy(self, params):
        return [200, "image/jpeg", b"", ""]

    def destroy(self):
        pass
