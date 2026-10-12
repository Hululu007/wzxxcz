# coding=utf-8
"""
被窝网 beiwowang.com 完整TVBOX/影视仓 Python爬虫
适配：webhtv / FongMi / TVBox 系列壳
✅ 内置中转页share解析，**Python内部直接解析出m3u8，不再依赖客户端parse=1**
✅ 不再交给Java层处理中转，playerContent直接返回真实播放地址
⚠️ 站点CDN存在时效防盗链：m3u8链接短期有效，每次播放需要实时拉取share页面
⚠️ 仅用于本地技术学习，严禁商用，注意版权风险
"""
import re
import json
import urllib.parse
import requests
from lxml import etree
from base.spider import Spider

class Spider(Spider):
    def __init__(self):
        self.name = "被窝网"
        self.host = "https://www.beiwowang.com"
        self.session = requests.Session()
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.host
        }
        # 分类ID映射
        self._cat_map = {
            "1": "dianying",
            "2": "lianxuju",
            "3": "zongyi",
            "4": "dongman",
            "5": "duanju",
        }
        # 正则：抓取player_aaaa
        self.RE_PLAYER_AAAA = re.compile(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*;', re.S | re.I)
        # 正则：抓取share页面里面 var main="xxx"
        self.RE_MAIN = re.compile(r'var\s+main\s*=\s*"([^"]+)"', re.S | re.I)

    def getName(self):
        return self.name

    def init(self, extend=''):
        pass

    def _get(self, url, params=None, referer=None):
        """GET请求，支持自定义referer"""
        headers = self.header.copy()
        if referer:
            headers["Referer"] = referer
        r = self.session.get(url, headers=headers, params=params, timeout=20, allow_redirects=True)
        r.encoding = 'utf-8'
        return r.text

    def _fix_url(self, url):
        """相对路径转绝对链接"""
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        return url

    def _parse_video_card(self, card):
        """解析单个视频卡片"""
        try:
            a_tag = card.xpath('.//a[@class="link"]')
            if not a_tag:
                return None
            a = a_tag[0]
            href = a.get("href", "")
            vod_id = self._fix_url(href)
            title = a.get("title", "").strip()

            img = a.xpath('.//img[@class="lazyload"]')
            vod_pic = ""
            if img:
                vod_pic = img[0].get("data-original", "") or img[0].get("src", "")
            vod_pic = self._fix_url(vod_pic)

            tag1_elem = card.xpath('.//div[@class="tag1"]/text()')
            vod_remarks = tag1_elem[0].strip() if tag1_elem else ""

            tag2_elem = card.xpath('.//p[@class="tag2"]/text()')
            vod_year = ""
            if tag2_elem:
                tag2_txt = tag2_elem[0].strip()
                m_year = re.search(r'(\d{4})', tag2_txt)
                if m_year:
                    vod_year = m_year.group(1)

            if not title:
                h3_elem = card.xpath('.//h3/text()')
                if h3_elem:
                    title = h3_elem[0].strip()

            return {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
                "vod_year": vod_year
            }
        except Exception:
            return None

    def _parse_video_list(self, html):
        """解析列表页全部视频"""
        videos = []
        try:
            root = etree.HTML(html)
            cards = root.xpath('//div[contains(@class,"grid-carditem")]')
            for card in cards:
                item = self._parse_video_card(card)
                if item and item.get("vod_name"):
                    videos.append(item)
        except Exception:
            pass
        return videos

    def _parse_pagecount(self, html):
        """解析分页最大页码"""
        total = 1
        try:
            root = etree.HTML(html)
            page_links = root.xpath('//div[@class="pages-box"]//ul//a/@href')
            for link in page_links:
                m = re.search(r'--------(\d+)---/', link)
                if m:
                    p = int(m.group(1))
                    if p > total:
                        total = p
        except Exception:
            pass
        return total

    # ========== 首页 ==========
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

    # ========== 分类列表 ==========
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

    # ========== 详情页 ==========
    def detailContent(self, ids):
        try:
            vod_id = str(ids[0])
            detail_url = self._fix_url(vod_id)
            html = self._get(detail_url)
            root = etree.HTML(html)

            vod_name = ""
            h1 = root.xpath('//div[@class="movie-info"]/h1/text()')
            if h1:
                vod_name = h1[0].strip()
            if not vod_name:
                title_tag = root.xpath('//title/text()')
                if title_tag:
                    vod_name = title_tag[0].split("_")[0].strip()

            vod_pic = ""
            pic_img = root.xpath('//div[@class="movie-poster"]//img')
            if pic_img:
                vod_pic = pic_img[0].get("data-original") or pic_img[0].get("src", "")
            vod_pic = self._fix_url(vod_pic)

            vod_year = ""
            meta_year = re.search(r'(\d{4})', html)
            if meta_year:
                vod_year = meta_year.group(1)

            vod_content = ""
            desc_text = root.xpath('//div[@class="movie-description"]/text()')
            if desc_text:
                vod_content = "\n".join([x.strip() for x in desc_text if x.strip()])

            play_href = root.xpath('//div[@class="movie-play"]//a/@href')
            play_from = []
            play_urls = []
            if play_href:
                ep_links = root.xpath('//div[@class="tab-content"]//ul//li//a')
                ep_list = []
                for a in ep_links:
                    ep_title = a.get("title", "").strip()
                    ep_href = self._fix_url(a.get("href", ""))
                    if ep_title and ep_href:
                        ep_list.append(f"{ep_title}${ep_href}")
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

    # ========== 重点：播放解析【内置share中转解析，直接返回m3u8】 ==========
    def playerContent(self, flag, id, vipFlags):
        """
        完整链路：播放页 -> player_aaaa拿到share链接 -> 请求share页面 -> 提取var main得到m3u8
        返回真实m3u8，parse=0，壳直接播放，不需要客户端额外处理中转页
        """
        try:
            play_page_url = self._fix_url(id)
            # 1、请求播放页面，拿到player_aaaa
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

            # 2、请求share中转页面，提取var main
            share_html = self._get(share_url, referer=play_page_url)
            match_main = self.RE_MAIN.search(share_html)
            if not match_main:
                return {"parse":0, "url":"", "header":""}
            main_path = match_main.group(1)
            # 拼接完整m3u8地址
            if main_path.startswith("/"):
                from urllib.parse import urlparse
                share_parse = urlparse(share_url)
                base_domain = f"{share_parse.scheme}://{share_parse.netloc}"
                real_m3u8 = base_domain + main_path
            else:
                real_m3u8 = main_path

            # 3、返回结果：parse=0，壳直接播放，携带防盗链header
            return {
                "parse": 0,
                "playUrl": "",
                "url": real_m3u8,
                "header": json.dumps({
                    "User-Agent": self.header["User-Agent"],
                    "Referer": share_url
                })
            }
        except Exception as e:
            print("播放解析异常:", str(e))
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

    # ========== 壳要求固定方法，不能删除 ==========
    def isVideoFormat(self, url):
        return any(url.lower().endswith(fmt) for fmt in ['.m3u8', '.mp4', '.flv', '.ts', '.mkv', '.avi', '.mov'])

    def manualVideoCheck(self):
        pass

    def localProxy(self, params):
        return [200, "image/jpeg", b"", ""]

    def destroy(self):
        self.session.close()
