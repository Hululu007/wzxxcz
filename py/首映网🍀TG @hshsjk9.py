# coding=utf-8
"""
首映网 jiyaogroup.com | TVBox Python 爬虫 (V19.0 源码级精准解剖版)
解决大类聚合页内容变少、海报图片丢失的问题。采用区块独立提取法，确保一网打尽！
"""

import re
import sys
import json
import time
import urllib.parse

sys.path.append('..')

# ==========================================================
# 0. 基础环境与依赖导入
# ==========================================================
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
                    pool_connections=20, 
                    pool_maxsize=20, 
                    max_retries=3
                )
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 20)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[shouying]", *a)
            except Exception:
                pass

    Spider = _BaseSpider

# ==========================================================
# 1. 全局常量定义
# ==========================================================
HOST = "https://jiyaogroup.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = "https://pic.rmb.bdstatic.com/bjh/1e6518d6cd2d785aa65c1ff9a74b89b2.jpeg"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ==========================================================
# 2. 分类定义 (完全对齐首页导航)
# ==========================================================
CLASSES = [
    {"type_id": "dianying",    "type_name": "电影"},
    {"type_id": "dianshiju",   "type_name": "电视剧"},
    {"type_id": "zongyi",      "type_name": "综艺"},
    {"type_id": "dongman",     "type_name": "动漫"},
    {"type_id": "donghuapian", "type_name": "动画片"},
    {"type_id": "duanju",      "type_name": "短剧"},
]

# ==========================================================
# 3. 全量暴力展开的筛选字典 (完美还原网页)
# ==========================================================
_SUB_CLASS_DIANYING = [
    {"n": "全部", "v": ""}, {"n": "动作", "v": "dongzuo"}, {"n": "喜剧", "v": "xiju"}, 
    {"n": "爱情", "v": "aiqing"}, {"n": "科幻", "v": "kehuan"}, {"n": "恐怖", "v": "kongbu"}, 
    {"n": "剧情", "v": "juqing"}, {"n": "战争", "v": "zhanzheng"}, {"n": "纪录片", "v": "jilu"}, 
    {"n": "动画", "v": "donghua"}
]

_SUB_CLASS_DIANSHIJU = [
    {"n": "全部", "v": ""}, {"n": "古装", "v": "guzhuang"}, {"n": "战争", "v": "zhanzheng"}, 
    {"n": "青春偶像", "v": "qingchunouxiang"}, {"n": "喜剧", "v": "xiju"}, {"n": "家庭", "v": "jiating"}, 
    {"n": "犯罪", "v": "fanzui"}, {"n": "动作", "v": "dongzuo"}, {"n": "奇幻", "v": "qihuan"}, 
    {"n": "剧情", "v": "juqing"}, {"n": "历史", "v": "lishi"}, {"n": "经典", "v": "jingdian"}, 
    {"n": "乡村", "v": "xiangcun"}, {"n": "情景", "v": "qingjing"}, {"n": "商战", "v": "shangzhan"}, 
    {"n": "网剧", "v": "wangju"}, {"n": "其他", "v": "qita"}
]

_SUB_CLASS_ZONGYI = [
    {"n": "全部", "v": ""}, {"n": "真人秀", "v": "zhenrenxiu"}, {"n": "脱口秀", "v": "tuokouxiu"}, 
    {"n": "国产综艺", "v": "guochan"}, {"n": "喜剧", "v": "xiju"}, {"n": "晚会", "v": "wanhui"}, 
    {"n": "音乐", "v": "yinyue"}, {"n": "游戏", "v": "youxi"}
]

_SUB_CLASS_DONGMAN = [
    {"n": "全部", "v": ""}, {"n": "动画", "v": "donghua"}, {"n": "冒险", "v": "maoxian"}, 
    {"n": "喜剧", "v": "xiju"}, {"n": "奇幻", "v": "qihuan"}, {"n": "剧情", "v": "juqing"}, 
    {"n": "科幻", "v": "kehuan"}, {"n": "动作", "v": "dongzuo"}
]

_SUB_CLASS_DONGHUAPIAN = [{"n": "全部", "v": ""}]

_SUB_CLASS_DUANJU = [
    {"n": "全部", "v": ""}, {"n": "AI漫剧", "v": "aimanju"}, {"n": "短剧", "v": "duanju"}, 
    {"n": "剧情", "v": "juqing"}, {"n": "爱情", "v": "aiqing"}, {"n": "爽文", "v": "shuangwen"}
]

_SUB_CLASS_DICT = {
    "dianying": _SUB_CLASS_DIANYING,
    "dianshiju": _SUB_CLASS_DIANSHIJU,
    "zongyi": _SUB_CLASS_ZONGYI,
    "dongman": _SUB_CLASS_DONGMAN,
    "donghuapian": _SUB_CLASS_DONGHUAPIAN,
    "duanju": _SUB_CLASS_DUANJU
}

_AREAS = [
    {"n": "全部", "v": ""}, 
    {"n": "内地", "v": "内地"}, 
    {"n": "韩国", "v": "韩国"}, 
    {"n": "香港", "v": "香港"}, 
    {"n": "台湾", "v": "台湾"}, 
    {"n": "日本", "v": "日本"}, 
    {"n": "美国", "v": "美国"}, 
    {"n": "泰国", "v": "泰国"}, 
    {"n": "英国", "v": "英国"}, 
    {"n": "新加坡", "v": "新加坡"}, 
    {"n": "其他", "v": "其他"}
]

_YEARS = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

_LANGS = [
    {"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"},
    {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"},
    {"n": "日语", "v": "日语"}, {"n": "其它", "v": "其它"}
]

_LETTERS = [{"n": "全部", "v": ""}] + [{"n": chr(i), "v": chr(i)} for i in range(65, 91)] + [{"n": "0-9", "v": "0-9"}]

_SORTS = [{"n": "按时间", "v": "time"}, {"n": "按人气", "v": "hits"}, {"n": "按评分", "v": "score"}]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "剧情", "value": _SUB_CLASS_DICT.get(tid, [])},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "lang", "name": "语言", "value": _LANGS},
        {"key": "letter", "name": "字母", "value": _LETTERS},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]

# ==========================================================
# 4. 正则表达式矩阵
# ==========================================================
# 核心算法：找到所有 <li> 标签（忽略换行），逐行解析里面的属性
_RE_LI_BLOCK = re.compile(r'<li[\s\S]*?</li>', re.I)
_RE_HREF = re.compile(r'href="(/voddetail/[^"]+)"', re.I)
_RE_TITLE = re.compile(r'title="([^"]+)"', re.I)
_RE_PIC_ORIGINAL = re.compile(r'data-original="([^"]+)"', re.I)
_RE_PIC_SRC = re.compile(r'src="([^"]+)"', re.I)

_RE_H1_BLOCK = re.compile(r'<h1 class="title">([\s\S]*?)</h1>', re.I)
_RE_H1_SCORE = re.compile(r'<span class="score[^"]*">([\d.]+)</span>', re.I)
_RE_PIC_DETAIL = re.compile(r'<div class="stui-content__thumb">[\s\S]*?<img[^>]*?data-original="([^"]+)"', re.S | re.I)
_RE_INTRO_BLOCK = re.compile(r'<p class="desc hidden-xs">\s*<span class="left text-muted">简介：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_INTRO_TAIL = re.compile(r'想看更多的.*?请关注我们的网站：[\s\S]*$', re.S | re.I)
_RE_DIRECTOR_TAG = re.compile(r'导演：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_ACTOR_TAG = re.compile(r'主演：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_TYPE_TAG = re.compile(r'类型：</span>([\s\S]*?)<span class="split-line">', re.S | re.I)
_RE_AREA_TAG = re.compile(r'地区：</span>([\s\S]*?)<span class="split-line">', re.S | re.I)
_RE_YEAR_TAG = re.compile(r'年份：</span>([\s\S]*?)</p>', re.S | re.I)
_RE_EPISODE_LI = re.compile(r'<li\s*[^>]*><a\s+href="(/vodplay/[^"]+?-(\d+)-(\d+)\.html)"[^>]*title="([^"]+)"', re.I)
_RE_TABS = re.compile(r'<a data-toggle="tab" href="#down(\d+)">([^<]+)</a>', re.I)
_RE_PLAYER_JSON = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)
_RE_IFRAME_SRC = re.compile(r'<iframe[^>]*src="([^"]+)"', re.I)
_RE_PAGE_NUM = re.compile(r'<span class="num">\d+/(\d+)</span>')
_RE_PAGE_TAIL = re.compile(r'href="[^"]*?(\d+)\.html">尾页')


# ==========================================================
# 5. 主爬虫类
# ==========================================================
class Spider(Spider):

    def getName(self):
        return "首映网"

    def init(self, extend=""):
        self.site_url = HOST
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}

    def _fetch(self, url, timeout=20):
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=timeout)
            return rsp.text or ""
        except Exception as e:
            self.log(f"请求失败 {url} -> {e}")
            return ""

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        return s.replace("&nbsp;", " ").replace("\xa0", " ").replace("&amp;", "&").strip()

    def _fix_pic(self, url):
        if not url or url.startswith("file:///") or url.strip() == "/":
            return self.default_pic
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        return self.site_url + url

    # ==========================================================
    # 核心解析：区块独立提取 (专杀内容变少和丢图)
    # ==========================================================
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        # 寻找到所有的 li 区块
        li_blocks = _RE_LI_BLOCK.findall(html)
        
        for block in li_blocks:
            # 必须包含 /voddetail/ 才是视频卡片
            if "/voddetail/" not in block:
                continue
                
            m_href = _RE_HREF.search(block)
            if not m_href:
                continue
                
            href = m_href.group(1).replace("&amp;", "&")
            if href in seen:
                continue
                
            # 提取标题
            m_title = _RE_TITLE.search(block)
            title = self._clean(m_title.group(1)) if m_title else "未知视频"
            
            # 提取图片，优先 original，其次 src
            pic = self.default_pic
            m_pic = _RE_PIC_ORIGINAL.search(block)
            if not m_pic:
                m_pic = _RE_PIC_SRC.search(block)
            if m_pic:
                pic = self._fix_pic(m_pic.group(1))
                
            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": pic,
                "vod_remarks": "",
            })
            seen.add(href)

        return videos

    def _extract_page_count(self, html):
        if not html:
            return 1
        m_num = _RE_PAGE_NUM.search(html)
        if m_num:
            try: return int(m_num.group(1))
            except: pass
        m_tail = _RE_PAGE_TAIL.search(html)
        if m_tail:
            try: return int(m_tail.group(1))
            except: pass
        return 1

    # ==========================================================
    # 接口 1: 首页内容
    # ==========================================================
    def homeContent(self, filter=False):
        html = self._fetch(self.site_url + "/")
        videos = self._extract_videos(html)
        return {"class": CLASSES, "filters": FILTERS, "list": videos}

    # ==========================================================
    # 接口 2: 分类内容
    # ==========================================================
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try: extend = json.loads(extend)
            except: extend = {}
        if not extend:
            extend = {}

        # 清理空值
        ext = {k: v for k, v in extend.items() if v not in ("", None, "全部")}

        cid = ext.get("class") or tid
        cls_param = "" if ext.get("class") == cid else ext.get("class", "")
        page_str = "" if page <= 1 else str(page)

        url = (
            f"{self.site_url}/vodshow/{cid}-{ext.get('area','')}-{ext.get('lang','')}-"
            f"{ext.get('letter','')}-{ext.get('sort','time')}-{cls_param}--------{page_str}---{ext.get('year','')}.html"
        )
        
        self.log("请求分类: " + url)
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pagecount = self._extract_page_count(html)

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 30,
            "total": 999
        }

    # ==========================================================
    # 接口 3: 搜索内容
    # ==========================================================
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        
        if page <= 1:
            url = f"{self.site_url}/vodsearch/-------------.html?wd={keyword}"
        else:
            url = f"{self.site_url}/vodsearch/--------{page}---.html?wd={keyword}"
            
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pagecount = self._extract_page_count(html)
        
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 30,
            "total": 999
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ==========================================================
    # 接口 4: 详情内容
    # ==========================================================
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
            
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self.site_url + vod_id
        
        html = self._fetch(url)
        if not html:
            return {"list": []}

        name = ""
        score = ""
        m_h1 = _RE_H1_BLOCK.search(html)
        if m_h1:
            raw_h1 = m_h1.group(1)
            m_score = _RE_H1_SCORE.search(raw_h1)
            if m_score:
                score = m_score.group(1)
            name = self._clean(re.sub(r'<span class="score[^"]*">[\d.]+</span>', '', raw_h1))
        name = name or vod_id

        pic = self.default_pic
        m_pic = _RE_PIC_DETAIL.search(html)
        if m_pic:
            pic = self._fix_pic(m_pic.group(1))

        content = ""
        m_intro = _RE_INTRO_BLOCK.search(html)
        if m_intro:
            content = self._clean(m_intro.group(1))
            content = _RE_INTRO_TAIL.sub("", content).strip()
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        def _grab_meta(regex):
            m = regex.search(html)
            if not m:
                return ""
            return self._clean(re.sub(r"<[^>]+>", " ", m.group(1))).strip(" ,，")
            
        director = _grab_meta(_RE_DIRECTOR_TAG)
        actor = _grab_meta(_RE_ACTOR_TAG)
        type_ = _grab_meta(_RE_TYPE_TAG)
        area = _grab_meta(_RE_AREA_TAG)
        year = _grab_meta(_RE_YEAR_TAG)

        tabs = {}
        for m in _RE_TABS.findall(html):
            tabs[m[0]] = self._clean(m[1])
            
        groups = {}
        for match in _RE_EPISODE_LI.findall(html):
            href, line, ep, ep_title = match
            href = href.replace("&amp;", "&")
            full_url = href if href.startswith("http") else self.site_url + href
            ep_name = self._clean(ep_title) or f"第{ep}集"
            groups.setdefault(line, []).append((ep_name, full_url))

        if not groups:
            return {"list": []}

        play_from = []
        play_url = []
        sorted_lines = sorted(groups.keys(), key=lambda x: int(x) if x.isdigit() else 999)
        
        for line in sorted_lines:
            eps = groups[line]
            alias = tabs.get(line, f"线路{line}")
            play_from.append(alias)
            episodes_str = "#".join(f"{n}${h}" for n, h in eps)
            play_url.append(episodes_str)

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_year": year,
            "vod_area": area,
            "vod_remarks": type_ or f"{len(groups)}条线路",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ==========================================================
    # 接口 5: 播放解析
    # ==========================================================
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self.site_url + id
        now = int(time.time())
        
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        m3u8 = ""
        
        if html:
            m_json = _RE_PLAYER_JSON.search(html)
            if m_json:
                try:
                    pa = json.loads(m_json.group(1))
                    if int(pa.get("encrypt", 0) or 0) == 0:
                        m3u8 = pa.get("url", "") or ""
                except Exception:
                    pass
            
            if not m3u8:
                m_iframe = _RE_IFRAME_SRC.search(html)
                if m_iframe:
                    m3u8 = m_iframe.group(1)

        if m3u8 and (m3u8.startswith("http") or m3u8.startswith("//")):
            if m3u8.startswith("//"): m3u8 = "https:" + m3u8
            res = {
                "parse": 0,
                "playUrl": "",
                "url": m3u8,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"}
            }
        else:
            res = {
                "parse": 1,
                "playUrl": "",
                "url": play_page,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"}
            }
            
        self._play_cache[play_page] = (now, res)
        return res

    # ==========================================================
    # 接口 6: 辅助
    # ==========================================================
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
