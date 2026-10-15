# coding=utf-8
"""
蝶卡影视 diekawang.com | TVBox Python爬虫
关键:
  - 解析页面JS中temLineList数组，base64解密m3u8地址
  - 首页/分类/搜索/详情/选集解析
  - parse=0直链播放，不需要嗅探
  - 简介添加提示前缀，缓存播放结果
"""
import re
import sys
import json
import time
import base64
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
            r = self._sess.get(url, headers=headers, timeout=timeout,** kw)
            r.encoding = 'utf-8'
            return r
        def log(self, *a, **kw):
            try:
                print("[diekawang]", *a)
            except Exception:
                pass
    Spider = _BaseSpider

HOST = "https://www.diekawang.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/static/picture/default.png"
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "vod/1/1/0",  "type_name": "电影"},
    {"type_id": "vod/1/2/0",  "type_name": "电视剧"},
    {"type_id": "vod/1/3/0",  "type_name": "综艺"},
    {"type_id": "vod/1/4/0",  "type_name": "动漫"},
    {"type_id": "vod/1/457/0","type_name": "短剧大全"},
    {"type_id": "vod/1/462/0","type_name": "体育"},
]
_SORTS = [{"n":"最新","v":"new"},{"n":"最热","v":"hot"}]
_YEARS = [{"n":"全部","v":""}]+[{"n":str(y),"v":str(y)} for y in range(2026,1999,-1)]
_AREAS = [
    {"n":"全部","v":""},
    {"n":"中国大陆","v":"大陆"},{"n":"美国","v":"美国"},
    {"n":"日本","v":"日本"},{"n":"韩国","v":"韩国"},
    {"n":"中国香港","v":"香港"},{"n":"中国台湾","v":"台湾"},
]
_FILTERS_MAP = {
    "vod/1/1/0":["全部","剧情","喜剧","动作","爱情","悬疑","犯罪","科幻"],
    "vod/1/2/0":["全部","都市","古装","谍战","家庭","爱情","悬疑"],
    "vod/1/3/0":["全部","真人秀","晚会","音乐","竞技"],
    "vod/1/4/0":["全部","国漫","日漫","冒险","奇幻"],
    "vod/1/457/0":["全部","爽文","古装","都市","爱情"],
    "vod/1/462/0":["全部","足球","篮球"],
}
FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key":"class","name":"分类","value":[{"n:x,"v":"" if x=="全部" else x} for x in _FILTERS_MAP.get(tid,["全部"])]},
        {"key":"area","name":"地区","value":_AREAS},
        {"key":"year","name":"年份","value":_YEARS},
        {"key":"sort","name":"排序","value":_SORTS},
    ]

# 正则
_RE_CARD = re.compile(r'<a href="([^"]+)"[^>]*>[\s\S]{0,220}?<img[^>]*?alt="([^"]+)"[^>]*?(?:data‑src|src)="([^"]+)"', re.S|re.I)
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>',re.S|re.I)
_RE_META_DESC = re.compile(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',re.I)
_RE_COVER_IMG = re.compile(r'<img data‑src="([^"]+)" alt=',re.I)
_RE_ACTOR_DIRECTOR = re.compile(r'<div class="actor‑list flex‑r‑s‑s">[\s\S]*?</div>',re.S)
# 关键：提取页面JS中的temLineList数组
_RE_TEMLINELIST = re.compile(r"var temLineList\s*=\s*(\[.*?\]);", re.S)

_LINE_PRIORITY = ["1080zyk"]
_LINE_ALIAS = {"1080zyk":"1080资源"}

class Spider(Spider):
    def getName(self):
        return "蝶卡影视"
    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User‑Agent":UA,
            "Accept‑Language":"zh‑CN,zh;q=0.9",
            "Referer":self.site_url+"/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init site=%s" % self.site_url)

    def _fetch(self,url,timeout=30,headers=None):
        try:
            h = dict(self.headers)
            if headers: h.update(headers)
            rsp = self.fetch(url,headers=h,timeout=timeout)
            text = rsp.text if hasattr(rsp,"text") else rsp.content.decode("utf‑8","ignore")
            return text
        except Exception as e:
            self.log("fetch fail %s → %s" %(url,e))
            return ""

    def _fix_url(self,url):
        if not url: return ""
        url = url.strip()
        if url.startswith("//"): return "https:"+url
        if url.startswith("http"): return url
        if url.startswith("/"): return self.site_url+url
        return urllib.parse.urljoin(self.site_url+"/",url)

    def _clean(self,s):
        if not s: return ""
        s = re.sub(r"<br\s*/?>","\n",s,flags=re.I)
        s = re.sub(r"<[^>]+>","",s)
        s = s.replace("&nbsp;"," ").replace("\xa0"," ")
        s = s.replace("&amp;","&").replace("&quot;",'"').replace("&#39;","'")
        s = re.sub(r"\s+"," ",s).strip()
        return s

    def _extract_videos(self,html):
        videos = []
        seen=set()
        matches = _RE_CARD.findall(html)
        for href,name,pic in matches:
            href = self._fix_url(href)
            if href in seen: continue
            seen.add(href)
            videos.append({
                "vod_id":href,
                "vod_name":self._clean(name)[:100],
                "vod_pic":self._fix_url(pic) or self.default_pic,
                "vod_remarks":""
            })
        return videos

    def _page_count(self,html):
        pg = re.findall(r'page=(\d+)',html)
        if pg:
            try: return max(int(x) for x in pg)+1
            except Exception: pass
        return 9999

    def homeContent(self,filter=False):
        return {"class":CLASSES,"filters":FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url+"/index.html")
        videos = self._extract_videos(html)
        return {"list":videos}

    def categoryContent(self,tid,pg,filter,extend):
        page = int(pg) if pg else 1
        if isinstance(extend,str):
            try: extend = json.loads(extend)
            except Exception: extend={}
        params={"page":page}
        url = "%s/%s?%s" % (self.site_url, tid.lstrip("/"), urllib.parse.urlencode(params))
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pc = self._page_count(html)
        return {"list":videos,"page":page,"pagecount":pc,"limit":24,"total":pc*24}

    def searchContent(self,key,quick,pg="1"):
        page=int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        url = f"{self.site_url}/search/index.html?wd={kw}&page={page}"
        html = self._fetch(url)
        videos = self._extract_videos(html)
        pc = self._page_count(html)
        return {"list":videos,"page":page,"pagecount":pc,"limit":24,"total":999}
    def searchContentPage(self,key,quick,pg="1"):
        return self.searchContent(key,quick,pg)

    def detailContent(self,ids):
        if not ids: return {"list":[]}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        html = self._fetch(url)
        if not html: return {"list":[]}

        #标题
        name=""
        mh1 = _RE_H1.search(html)
        if mh1: name = self._clean(mh1.group(1))
        if not name:
            mtitle = re.search(r"<title>(.*?)</title>",html,re.S)
            if mtitle: name = self._clean(mtitle.group(1).split("_")[0])
        name = name or vod_id

        #封面
        pic = self.default_pic
        mcover = _RE_COVER_IMG.search(html)
        if mcover: pic = self._fix_url(mcover.group(1))

        #简介
        content = ""
        mdesc = _RE_META_DESC.search(html)
        if mdesc: content = self._clean(mdesc.group(1))
        content = INTRO_PREFIX + "\n" + content if content else INTRO_PREFIX

        actor=""
        director=""
        #解析temLineList数组
        m_tem = _RE_TEMLINELIST.search(html)
        groups = {}
        if m_tem:
            try:
                arr_raw = m_tem.group(1)
                temLineList = json.loads(arr_raw)
                ep_list = []
                for item in temLineList:
                    ep_name = item.get("subTitle","")
                    line_tag = item.get("tag","")
                    play_id = item.get("id","")
                    video_id = item.get("videoID","")
                    play_page_url = f"{self.site_url}/vod/player/{play_id}/{video_id}"
                    ep_list.append((ep_name, play_page_url))
                if ep_list:
                    groups["1080zyk"] = ep_list
            except Exception as e:
                self.log("解析temLineList失败: %s" % e)
        if not groups:
            return {"list":[]}

        sorted_origins = sorted(groups.keys(),key=lambda x:_LINE_PRIORITY.index(x) if x in _LINE_PRIORITY else 999)
        play_from = []
        play_url = []
        for origin in sorted_origins:
            eps = groups[origin]
            alias = _LINE_ALIAS.get(origin,origin)
            play_from.append(alias)
            play_url.append("#".join("%s$%s" %(n,h) for n,h in eps))

        return {"list":[{
            "vod_id":vod_id,
            "vod_name":name,
            "vod_pic":pic,
            "vod_content":content,
            "vod_actor":actor,
            "vod_director":director,
            "vod_score":"",
            "vod_remarks":f"{len(groups)}条线路",
            "vod_play_from":"$$$".join(play_from),
            "vod_play_url":"$$$".join(play_url),
        }]}

    def playerContent(self,flag,id,vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        now = int(time.time())
        if play_page in self._play_cache:
            ts,res = self._play_cache[play_page]
            if now‑ts < 600: return res
        html = self._fetch(play_page)
        real_m3u8 = ""
        m_tem = _RE_TEMLINELIST.search(html)
        if m_tem:
            try:
                arr_raw = m_tem.group(1)
                temLineList = json.loads(arr_raw)
                for item in temLineList:
                    file_str = item.get("file","")
                    if len(file_str)>3:
                        b64part = file_str[3:]
                        dec_b = base64.b64decode(b64part).decode("utf‑8")
                        real_m3u8 = urllib.parse.unquote(dec_b)
                        break
            except Exception as e:
                self.log("解码m3u8失败 %s" % e)
        if real_m3u8:
            res = {
                "parse":0,
                "playUrl":"",
                "url":real_m3u8,
                "header":{"User‑Agent":UA,"Referer":self.site_url+"/"}
            }
            self._play_cache[play_page]=(now,res)
            return res
        #兜底嗅探
        res = {"parse":1,"playUrl":"","url":play_page,"header":{"User‑Agent":UA,"Referer":self.site_url+"/"}}
        self._play_cache[play_page]=(now,res)
        return res

    def localProxy(self,param):
        try:
            url=""
            if isinstance(param,dict):
                url = param.get("url","")
            else:
                for pair in str(param).split("&"):
                    if "=" in pair:
                        k,v = pair.split("=",1)
                        if k=="url": url=v
            if not url: return [200,"image/jpeg",b"",""]
            url = urllib.parse.unquote(url) if "%" in url else url
            url = self._fix_url(url)
            rsp = self.fetch(url,headers={"User‑Agent":UA,"Referer":self.site_url+"/"},timeout=15)
            ctype = rsp.headers.get("Content‑Type","image/jpeg")
            if not ctype.startswith("image/"): ctype="image/jpeg"
            return [200,ctype,rsp.content,""]
        except Exception:
            return [200,"image/jpeg",b"",""]

    def isVideoFormat(self,url):
        return ".m3u8" in url or ".mp4" in url
    def manualVideoCheck(self):
        return False
    def destroy(self):
        pass
    def close(self):
        self.destroy()
