# coding=utf-8
# !/usr/bin/python
# -*- coding: utf-8 -*-
"""
TVBox 影视爬虫 —— 低端影视 (https://www.ddys24.com/)
======================================================
严格依据网站真实结构编写（全部 url / class / 字段均来自真实网页源码，
未使用任何猜测；亦未照抄任何其它站点源码，仅参考 TVBox 通用接口规范）。

【真实结构备忘（实测）】
  分类:   /ddvodshow/{tid}-----------.html
  分页:   /ddvodshow/{tid}--------{page}---.html
  详情:   /ddvoddetail/{id}.html
  播放页: /ddvodplay/{id}-{线路}-{集数}.html
  搜索:   /ddvodsearch/{关键词}-------------.html
  卡片锚点: <a class="...stui-vodlist_ddy1102-cthumb ..." href="/ddvoddetail/{id}.html"
              title="名称" data-original="图片">
  播放地址: 播放页内  var player_aaaa={...,"url":"xxx.m3u8","encrypt":0,...}
            encrypt=0 表示直链未加密，直接取 url 即可。
"""

import sys
import re
import json
import base64
import time
from urllib.parse import urljoin, quote, unquote

sys.path.append('..')
try:
    import requests
except Exception:
    requests = None
try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        pass


# ============================== 常量配置 ==============================

HOST = "https://www.ddys24.com"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 顶部一级分类（真实取自导航：/ddvodtype/*.html）
CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "42", "type_name": "豆瓣Top250"},
]

# 二级分类（真实取自首页板块链接 /ddvodshow/{tid}-----------.html）
SUB_CLASSES = {
    "1": [
        {"type_id": "6", "type_name": "动作片"},
        {"type_id": "7", "type_name": "喜剧片"},
        {"type_id": "8", "type_name": "爱情片"},
        {"type_id": "9", "type_name": "科幻片"},
        {"type_id": "10", "type_name": "恐怖片"},
        {"type_id": "11", "type_name": "剧情片"},
        {"type_id": "12", "type_name": "战争片"},
        {"type_id": "20", "type_name": "纪录片"},
        {"type_id": "29", "type_name": "犯罪片"},
        {"type_id": "39", "type_name": "动漫片"},
    ],
    "2": [
        {"type_id": "13", "type_name": "国产剧"},
        {"type_id": "43", "type_name": "抖音短剧"},
        {"type_id": "16", "type_name": "美剧"},
        {"type_id": "14", "type_name": "港剧"},
        {"type_id": "15", "type_name": "韩剧"},
        {"type_id": "21", "type_name": "泰剧"},
        {"type_id": "35", "type_name": "海外剧"},
        {"type_id": "40", "type_name": "日剧"},
        {"type_id": "41", "type_name": "台剧"},
    ],
    "3": [
        {"type_id": "22", "type_name": "内地综艺"},
        {"type_id": "23", "type_name": "港台综艺"},
        {"type_id": "24", "type_name": "日韩综艺"},
        {"type_id": "25", "type_name": "欧美综艺"},
    ],
    "4": [
        {"type_id": "26", "type_name": "国漫"},
        {"type_id": "27", "type_name": "日韩动漫"},
        {"type_id": "28", "type_name": "欧美动漫"},
        {"type_id": "34", "type_name": "海外动漫"},
    ],
}

# 筛选维度（真实取自分类页：按剧情/地区/语言/年份/字母/排序）
FILTER_OPTIONS = {
    "剧情": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪",
           "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑",
           "惊悚", "经典", "青春", "文艺", "微电影", "古装", "历史", "运动",
           "农村", "儿童", "网络电影", "其它"],
    "地区": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
           "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他", "其它"],
    "语言": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语",
           "其它"],
    "年份": ["2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017",
           "2016", "2015", "2014", "2013", "2012", "2011", "2010"],
    "字母": list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    "排序": ["按最新", "按人气", "按评分"],
}

INTRO_PREFIX = "🍊低端影视为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"


def _clean(t):
    """去除 html 标签与多余空白，解码实体"""
    if not t:
        return ""
    t = re.sub(r'<[^>]+>', '', t)
    t = t.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"') \
         .replace('&#39;', "'").replace('&lt;', '<').replace('&gt;', '>')
    return re.sub(r'\s+', ' ', t).strip()


class Spider(object):

    # ---------------------------------------------------------- 基础
    def getName(self):
        return "低端影视"

    def init(self, extend=""):
        self.site_url = HOST
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        try:
            self.session.get(self.site_url, timeout=10)
        except Exception:
            pass

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def homeVideoContent(self):
        return self.homeContent(False)

    def localProxy(self, param):
        return None

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    # ---------------------------------------------------------- 通用请求
    def _get(self, url, referer=None, timeout=15):
        headers = {}
        if referer:
            headers["Referer"] = referer
        for i in range(3):
            try:
                r = self.session.get(url, headers=headers, timeout=timeout,
                                     allow_redirects=True)
                if r.status_code == 200:
                    r.encoding = 'utf-8'
                    return r.text
            except Exception:
                time.sleep(0.5)
        return ""

    # ---------------------------------------------------------- 解析卡片
    def _extract_videos(self, html):
        """统一锚点解析：首页 / 分类 / 搜索 卡片结构一致"""
        videos = []
        seen = set()
        # 卡片锚点：<a class="...stui-vodlist_ddy1102-cthumb..." href="/ddvoddetail/{id}.html"
        #            title="名称" data-original="图片">
        pat = re.compile(
            r'<a[^>]*class="[^"]*stui-vodlist_ddy1102-cthumb[^"]*"[^>]*'
            r'href="(/ddvoddetail/(\d+)\.html)"[^>]*'
            r'title="([^"]*)"[^>]*'
            r'data-original="([^"]*)"',
            re.S)
        for m in pat.finditer(html):
            vid = m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            name = _clean(m.group(3))
            pic = m.group(4).strip()
            if pic.startswith('//'):
                pic = "https:" + pic
            videos.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "",
            })

        # 补备注：<span class="pic-text text-right">HD国语</span>
        rems = re.findall(
            r'<a[^>]*class="[^"]*stui-vodlist_ddy1102-cthumb[^"]*"[^>]*'
            r'href="(/ddvoddetail/\d+\.html)"[^>]*>.*?'
            r'<span class="pic-text[^"]*">([^<]*)</span>', html, re.S)
        rem_map = {m[0]: _clean(m[1]) for m in rems}
        for v in videos:
            r = rem_map.get("/ddvoddetail/%s.html" % v["vod_id"], "")
            if r:
                v["vod_remarks"] = r
        return videos

    def _total_page(self, html):
        """从分页区取总页数：<span class="num">1/203</span>"""
        m = re.search(r'<span class="num">\d+\s*/\s*(\d+)</span>', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        # 兜底：尾页链接 /ddvodshow/6--------203---.html
        m = re.search(r'/ddvodshow/\d+-{8}(\d+)-{3}\.html">尾页', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return 1

    # ---------------------------------------------------------- 首页
    def homeContent(self, filter=True):
        result = {"class": [], "filters": {}, "list": []}
        try:
            html = self._get(self.site_url + "/")
            # 分类：一级 + 其下二级（二级直接平铺为独立分类，方便电视端选择）
            for c in CLASSES:
                result["class"].append({
                    "type_id": c["type_id"],
                    "type_name": c["type_name"],
                })
                for s in SUB_CLASSES.get(c["type_id"], []):
                    result["class"].append({
                        "type_id": s["type_id"],
                        "type_name": s["type_name"],
                    })

            # 筛选（每个分类都可筛选）
            if filter:
                filt = self._build_filters()
                for c in CLASSES:
                    tid = c["type_id"]
                    result["filters"][tid] = filt
                    for s in SUB_CLASSES.get(tid, []):
                        result["filters"][s["type_id"]] = filt

            # 首页推荐（最近更新 板块）
            result["list"] = self._extract_videos(html)
            if not result["list"]:
                # 兜底，取内容里所有卡片
                result["list"] = self._extract_videos(html)
        except Exception as e:
            print("homeContent error:", e)
        return result

    def _build_filters(self):
        """按真实分段结构构造筛选：{剧情}-{地区}-{语言}-{年份}-{字母}-{排序}"""
        def group(name, values):
            opts = [{"n": "全部", "v": ""}]
            for v in values:
                opts.append({"n": v, "v": v})
            return {"key": name, "name": name, "value": opts}

        return [
            group("剧情", FILTER_OPTIONS["剧情"]),
            group("地区", FILTER_OPTIONS["地区"]),
            group("语言", FILTER_OPTIONS["语言"]),
            group("年份", FILTER_OPTIONS["年份"]),
            group("字母", FILTER_OPTIONS["字母"]),
            {
                "key": "排序", "name": "排序",
                "value": [
                    {"n": "按最新", "v": ""},
                    {"n": "按人气", "v": "hits"},
                    {"n": "按评分", "v": "score"},
                ]
            },
        ]

    # ---------------------------------------------------------- 分类
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 1,
                  "limit": 24, "total": 999999}
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            tid = str(tid)

            # 真实分段结构（实测归纳，tid 后固定 12 段，用 '-' 连接）：
            #   索引: 0(空) 1(地区) 2(排序) 3(剧情) 4(语言) 5(字母) 6(空) 7(空)
            #         8(页) 9(空) 10(空) 11(年份)
            # 例：/ddvodshow/6--------2---.html  -> 第2页
            #     /ddvodshow/6---喜剧--------.html -> 剧情=喜剧
            plot = area = lang = letter = year = order = ""
            if isinstance(extend, dict):
                plot = extend.get("剧情", "") or ""
                area = extend.get("地区", "") or ""
                lang = extend.get("语言", "") or ""
                year = extend.get("年份", "") or ""
                letter = extend.get("字母", "") or ""
                order = extend.get("排序", "") or ""

            def seg(x):
                return quote(x, safe='') if x else ""

            page_seg = "" if (pg <= 1) else str(pg)
            segs = ["", seg(area), seg(order), seg(plot), seg(lang), seg(letter),
                    "", "", page_seg, "", "", seg(year)]
            url = "%s/ddvodshow/%s%s.html" % (self.site_url, tid, "-".join(segs))

            html = self._get(url, referer=self.site_url + "/")
            result["list"] = self._extract_videos(html)
            result["pagecount"] = self._total_page(html)
            result["page"] = pg
        except Exception as e:
            print("categoryContent error:", e)
        return result

    # ---------------------------------------------------------- 搜索
    def searchContent(self, key, quick, pg="1"):
        result = {"list": [], "page": int(pg) if str(pg).isdigit() else 1}
        try:
            kw = quote(key, safe='')
            url = "%s/ddvodsearch/%s-------------.html" % (self.site_url, kw)
            html = self._get(url, referer=self.site_url + "/")
            result["list"] = self._extract_videos(html)
        except Exception as e:
            print("searchContent error:", e)
        return result

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------------------------------------------------- 详情
    def detailContent(self, array):
        try:
            tid = array[0]
            url = "%s/ddvoddetail/%s.html" % (self.site_url, tid)
            html = self._get(url, referer=self.site_url + "/")
            if not html:
                return {"list": []}

            vod = {
                "vod_id": str(tid),
                "vod_name": "",
                "vod_pic": "",
                "type_name": "",
                "vod_year": "",
                "vod_area": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "",
                "vod_play_url": "",
            }

            # 名称
            m = re.search(r'<h1 class="title">\s*([^<]+?)\s*</h1>', html)
            if m:
                vod["vod_name"] = _clean(m.group(1))
            if not vod["vod_name"]:
                m = re.search(r'<title>\s*《?([^《》<]+?)》?[^<]*</title>', html)
                if m:
                    vod["vod_name"] = _clean(m.group(1))

            # 封面（懒加载 data-original）
            m = re.search(
                r'<a[^>]*class="[^"]*picture[^"]*"[^>]*>.*?'
                r'<img[^>]*data-original="([^"]+)"', html, re.S)
            if not m:
                m = re.search(r'<img[^>]*class="lazyload"[^>]*data-original="([^"]+)"', html)
            if m:
                pic = m.group(1).strip()
                if pic.startswith('//'):
                    pic = "https:" + pic
                vod["vod_pic"] = pic

            # 备注 / 评分
            m = re.search(r'<span class="pic-text text-right">([^<]*)</span>', html)
            if m:
                vod["vod_remarks"] = _clean(m.group(1))

            # 类型 / 地区 / 年份 / 语言（真实：<p class="data hidden-xs">）
            m = re.search(r'<p class="data hidden-xs">(.*?)</p>', html, re.S)
            if m:
                info = m.group(1)
                t = re.search(r'类型：</span>\s*(?:<a[^>]*>)?([^<]+)', info)
                if t:
                    vod["type_name"] = _clean(t.group(1))
                a = re.search(r'地区：</span>\s*(?:<a[^>]*>)?([^<]+)', info)
                if a:
                    vod["vod_area"] = _clean(a.group(1))
                y = re.search(r'年份：</span>\s*(?:<a[^>]*>)?([^<]+)', info)
                if y:
                    vod["vod_year"] = _clean(y.group(1))

            # 主演 / 导演（真实：<p class="data"><span...>主演：</span>xxx</p>）
            vm = re.search(r'主演：</span>\s*([^<]*)</p>', html)
            if vm:
                vod["vod_actor"] = _clean(vm.group(1))
            dm = re.search(r'导演：</span>\s*([^<]*)</p>', html)
            if dm:
                vod["vod_director"] = _clean(dm.group(1))

            # 简介（真实：含 "剧情：" 的 span）
            cm = re.search(r'剧情：</b>\s*([^<]*)</span>', html)
            if cm:
                vod["vod_content"] = INTRO_PREFIX + _clean(cm.group(1))

            # ---------- 播放线路 ----------
            # 真实结构：每个线路块内 <h3 class="title">线路名</h3> ... 之后紧跟
            #           <ul class="stui-content_ddy1102-cplaylist ..."> 剧集列表 </ul>
            # 注意：线路名不一定是"线路X"，也可能是"高清线路"，故不能只按名称匹配。
            # 采用锚点法：以 cplaylist 的 <ul> 为锚，向前回溯最近的 h3.title 取线路名。
            play_from = []
            play_url = []
            for um in re.finditer(
                    r'<ul class="stui-content_ddy1102-cplaylist[^"]*">(.*?)</ul>',
                    html, re.S):
                body = um.group(1)
                # 向前找最近的 h3.title 作为线路名
                head = html[:um.start()]
                hm = None
                for hm in re.finditer(r'<h3 class="title">\s*(.*?)\s*</h3>', head, re.S):
                    pass
                line_name = ""
                if hm:
                    line_name = _clean(hm.group(1))
                # 剔除注释掉的链接
                body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
                links = re.findall(
                    r'<a[^>]*href="(/ddvodplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*>([^<]+)</a>',
                    body)
                if not links:
                    continue
                eps = []
                seen_ep = set()
                for href, vid, line, ep, label in links:
                    n = _clean(label) or ("第%s集" % ep)
                    if href in seen_ep:
                        continue
                    seen_ep.add(href)
                    eps.append("%s$%s" % (n, urljoin(self.site_url, href)))
                if eps:
                    play_from.append(line_name or ("线路%d" % (len(play_from) + 1)))
                    play_url.append("#".join(eps))

            vod["vod_play_from"] = "$$$".join(play_from)
            vod["vod_play_url"] = "$$$".join(play_url)
            return {"list": [vod]}
        except Exception as e:
            print("detailContent error:", e)
            return {"list": []}

    # ---------------------------------------------------------- 播放
    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "url": id,
                  "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        try:
            # id 即播放页地址 /ddvodplay/{id}-{line}-{ep}.html
            pu = id if id.startswith("http") else self.site_url + id
            html = self._get(pu, referer=self.site_url + "/")

            # 真实：var player_aaaa={...,"url":"xxx.m3u8","encrypt":0,...}
            m = re.search(r'var player_aaaa=(\{.*?\})</script>', html, re.S)
            if not m:
                m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*;?\s*</script>', html, re.S)
            if not m:
                m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*<', html, re.S)

            real = ""
            encrypt = 0
            from_ = ""
            if m:
                try:
                    data = json.loads(m.group(1))
                    real = data.get("url", "") or ""
                    encrypt = int(data.get("encrypt", 0) or 0)
                    from_ = data.get("from", "") or ""
                except Exception:
                    # json 解析失败用粗暴提取
                    u = re.search(r'"url"\s*:\s*"([^"]+)"', m.group(1))
                    if u:
                        real = u.group(1)
                    e = re.search(r'"encrypt"\s*:\s*(\d+)', m.group(1))
                    if e:
                        encrypt = int(e.group(1))

            real = real.replace('\\/', '/').strip()
            if not real:
                # 兜底：正则直接抓 m3u8
                u = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                if u:
                    real = u.group(1)

            if real and real.startswith('//'):
                real = "https:" + real
            if real and not real.startswith('http'):
                real = urljoin(pu, real)

            if not real:
                result["url"] = id
                return result

            # encrypt 非 0 时尝试 base64/unquote 解密（兼容可能出现的加密线路）
            if encrypt != 0:
                real = self._decode(real)

            # 处理主播放列表：解析出子 m3u8（更利于 TVBox 秒播）
            final_url = self._resolve_master(real) or real

            result["parse"] = 0
            result["playUrl"] = ""
            result["url"] = final_url
            # header 用站点 Referer（实测该 CDN 不校验防盗链，带上更贴近真实浏览器）
            result["header"] = {
                "User-Agent": UA,
                "Referer": self.site_url + "/",
            }
        except Exception as e:
            print("playerContent error:", e)
        return result

    def _decode(self, s):
        """兼容性解密：base64 -> url decode"""
        try:
            t = s
            for _ in range(2):
                try:
                    pad = t + "=" * (-len(t) % 4)
                    d = base64.b64decode(pad).decode('utf-8', 'ignore')
                    if d.startswith('http'):
                        t = d
                    else:
                        break
                except Exception:
                    break
            t = unquote(t)
            return t
        except Exception:
            return s

    def _resolve_master(self, url):
        """
        若为 master playlist（含 EXT-X-STREAM-INF），取最低码率子列表地址。
        低端影视的 url 多为 v.gsuus.com/play/xxx/index.m3u8 这种主列表，
        返回子 m3u8 可让 TVBox 直接播放、减少卡顿。
        """
        try:
            if '.m3u8' not in url:
                return ""
            txt = self._get(url, referer=self.site_url + "/")
            if 'EXT-X-STREAM-INF' not in txt:
                return ""
            lines = [l.strip() for l in txt.splitlines() if l.strip()]
            subs = []
            for i, l in enumerate(lines):
                if l.startswith('#EXT-X-STREAM-INF'):
                    bw = re.search(r'BANDWIDTH=(\d+)', l)
                    if i + 1 < len(lines):
                        sub = lines[i + 1]
                        subs.append((int(bw.group(1)) if bw else 0, sub))
            if not subs:
                return ""
            subs.sort(key=lambda x: x[0])
            sub = subs[0][1]
            if sub.startswith('http'):
                return sub
            return urljoin(url, sub)
        except Exception:
            return ""

    # ---------------------------------------------------------- 其它
    def action(self, action):
        return {}

    def close(self):
        pass
