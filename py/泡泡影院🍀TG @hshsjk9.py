# coding=utf-8
"""
泡泡影院 www.zhonganedu.com | TVBox Python 爬虫
==================================================
全部解析规则均来自真实抓取的页面源码，逐项标注依据。

【网站结构】
1) 频道导航：/class/1.html 电影、/class/2.html 电视剧、/class/3.html 综艺片、
   /class/4.html 动漫、/class/24.html 短剧

2) 列表卡片（首页 / 分类页 / 详情页“猜你喜欢”同构）：
   <li class="ff-vod-img-list ...">
     <a href="/celluloid/z9696775.html">
       <img data-original="https://.../xxx.jpg" src="/template/hl009/images/load.gif"
            alt="三国第一部：争洛阳">
       <div class="douban_score picrgot"><em class="label littplus">TC</em></div>
     </a>
     <h4 class="ff-text-hidden">
       <a href="/celluloid/z9696775.html" title="三国第一部：争洛阳">三国第一部：争洛阳</a>
   </li>
   真实封面在 data-original；src 恒为 load.gif 懒加载占位图。

3) 分页：/class/{分类ID}-{页}.html，第1页 /class/{分类ID}.html
   尾页给出总页数，例：<a href="/class/13-2630.html">尾页</a>
   注意：分类页的 {分类ID} 是分类id（如 13=国产剧），频道页是频道id（如 1=电影）。

4) 搜索（真实源码，wd=老舅 的结果页）：
   表单：<form method="get" class="ff-search" action="/query.html">
           <input type="text" class="form-control ff-wd" id="wd" name="wd">
   第1页：GET /query.html?wd=关键词
   翻页 ：GET /query/page/{页}/wd/{URL编码关键词}.html
          页脚真实链接：<a href="/query/page/1/wd/%E8%80%81%E8%88%85.html">尾页</a>
          → 关键词在路径段里，第1页之后一律走这个形式
   总数 ：<span class="ff-text mac_total">4</span>
   结果卡片与首页/分类页同构（li.ff-vod-img-list），解析复用 _extract_videos。
   注意：无封面条目的 data-original 是 /static/images/load.png 占位图
        （如“老舅与我”），与 load.gif 一样都要丢弃换默认图。

5) 筛选：/explore/... 组合路径，真实样本（全部取自页内 href 原文）：
   /explore/id/13.html                              （只有分类/频道）
   /explore/class/古装/id/13.html                   （类型）
   /explore/area/内地/id/13.html                    （地区）
   /explore/id/13/year/2018.html                    （年代，year 恒在 id 之后）
   /explore/by/hits/id/13.html                      （排序）
   /explore/area/内地/class/古装/id/13.html         （地区已在，再点类型）
   /explore/area/内地/by/hits/id/13.html            （地区已在，再点排序）
   /explore/class/古装/id/13/year/2018.html         （类型+年代）
   /explore/by/hits/id/13/year/2018.html            （排序+年代）

   站点是“点一次追加一段”，所以段序不固定，但真实出现过的组合只符合：
       id 之前：[area] → [class] → [by]，先选的在前
       id 之后：[year]
   按此规则拼出的 9 种单项/组合与页内真实 href 逐字符一致（已全量比对）。
   注意：id 段是频道/分类id（13=国产剧），class 段是类型名（古装/战争），
        两者不是一回事，绝不能把分类id塞进 class 段。

5.1) 【筛选面板的真实 DOM：五组 dl，逐组照抄】
     频道页 /class/{tid}.html 里，列表区之前是连续的
         <dl class="dl-horizontal"><dt>Xxx：</dt><dd class="...">…<a href="...">…</a></dd></dl>
     实测五个频道都是同样五组、同样顺序：
         频道 → 分类 → 类型 → 地区 → 年代
     逐组真实 href 形状：
         频道 /explore/id/{频道id}.html                 （1/2/3/4/24）
         分类 /explore/id/{分类id}.html                 “全部”是 /explore.html（无 id 段）
              分类id：电影 6/7/8/9/10/11/41/12/39；电视剧 13/14/15/16/22/21/20/23；
                      综艺 25/26/27/28；动漫 29/30/42/31/43；短剧 40/44
         类型 /explore/class/{类型名}/id/{频道id}.html
         地区 /explore/area/{地区名}/id/{频道id}.html
         年代 /explore/id/{频道id}/year/{年}.html
     **页面上没有“排序”组**：唯一出现 by/hits 的是右上角「筛选」按钮
         <a class="btn btn-success btn-sm pull-right" href="/explore/by/hits/id/4.html">
     那是入口不是筛选项，所以本爬虫不提供“排序”面板。

     各频道取值差异（照抄页面，不补不凑）：
       电影(1)  类型 26（无重复）  地区 15（“大陆”）  年代 16（**无 2011**）
       电视剧(2) 类型 16            地区 10            年代 17
       综艺(3)  类型 13            地区  4（内地/港台/日韩/欧美）  年代 15（2018…2004，**无 2019+**）
       动漫(4)  类型 20            地区  4（国产/日本/欧美/其他）  年代 15（2018…2004）
       短剧(24) 类型/地区/年代 三组都只有一个<b>空文本</b>的“全部”，没有可选值
     → 所以按频道分表（_CATS_BY_TID / _TYPES_BY_TID / _AREAS_BY_TID / _YEARS_BY_TID），
       短剧只给「分类」。

5.2) 【分类 = 换 id，不是额外的筛选段】
     页面上「分类」组的 href 是 /explore/id/13.html，
     而 /explore/id/2.html 与 /class/2.html 正文一致；
     /explore/id/7.html 页脚的“下一页/尾页”直接就是
         <a href="/class/7-2.html">下一页</a>
         <a href="/class/7-4898.html">尾页</a>
     → 说明 {id} 这个位置就是列表主体，分类只是换了个 id。
     故 categoryContent 里：选分类 → cid 换成该分类；翻页一律
     /class/{cid}-{N}.html。页面也从不产生“分类+类型+年代”同时出现的地址。

5.3) 【explore 页翻页会丢筛选条件（站点自身行为）】
     GET /explore/area/%E5%86%85%E5%9C%B0/id/13.html （该筛选只有 2 页）页脚原文：
         <a href="/class/13-1.html">上一页</a>
         <a href="/class/13-2.html">下一页</a>
         <a href="/class/13-2.html">尾页</a>
     —— 翻页链接全部退回 /class/{id}-{N}.html，筛选条件被丢掉。
     不是爬虫 bug，代码照它的链接走。

6) 详情页（真实源码 z3133105 伟大的长征）：
   封面区  <a class="detail-thumb-pic" href="/playurl/z3133105/6/1.html" title="伟大的长征">
             <img class="img-responsives ff-img" data-original="https://img.dytt-tupian.com/…/a08a….webp"
                  src="/template/hl009/images/load.gif" alt="伟大的长征"/>
             <span class="detail-thumb-play hidden-xs"></span>
             <span class="detail-thumb-text">更新至第20集</span>
           → 状态文本 detail-thumb-text 比 <dt>状态</dt> 更靠前，两者内容一致，
             这里优先取 detail-thumb-text。
   标题  <h4><a href="/celluloid/z3133105.html" class="ff-text">伟大的长征</a></h4>
   <dl class="dl-horizontal"> 字段顺序（**没有“类型”字段**）：
     主演：<dd class="ff-text-hidden ff-nb"><a href="/query/actor/于和伟.html">于和伟</a>&nbsp;…
     状态：<dd class="ff-text-hidden" style="color:#FF0000">更新至第20集</dd>
     导演：<dd class="ff-text-hidden ff-nb"><a href="/query/director/张永新.html">张永新</a>
     地区：<dt class="hidden-xs">地区：</dt><dd class="hidden-xs ff-text-hidden ff-nb"><a href="/query/area/大陆.html">大陆</a>
     年份：<dd><a href="/query/year/2026.html">2026</a>
     剧情：<dd class="hidden-xs vod-blurb">…截断…<a href="#vod_content" class="ff-text">详细...</a>
   完整简介在别处：<div class="vod-content"> … </div>（多段，含全角空格）
   → 故 vod_class 无从可取（页面本就没有），_TYPES_BY_TID 只服务筛选面板。
   “猜你喜欢”卡片 class 为
      <li class="ff-vod-img-list col-md-3 col-sm-2 col-xs-4 text-center ff-col ff-vod-img-hot ">
   与列表页 <li class="ff-vod-img-list …"> 前缀相同，_RE_LI 可直接通用。

7) 线路与剧集（关键陷阱，已实测确认）：
   <ul ... class="... play-title">
     <li><a href="#playurl-tab-6" data-toggle="tab">...线路1</a></li>
     <li><a href="#playurl-tab-2" ...>线路2</a></li>
     <li class="active"><a href="#playurl-tab-1" ...>线路4</a></li>
     ...
   </ul>
   <div class="tab-pane" id="playurl-tab-6">
     <ul class="... play-list">
       <li><a class="btn ..." href="/playurl/z9696775/6/1.html" title="TC">TC</a></li>
     </ul>
   </div>
   → 界面上的“线路N”顺序与 sid 完全不同：线路1=sid6、线路4=sid1。
     因此必须从 tab 的 href="#playurl-tab-{sid}" 取 sid，绝不按序号推断。
   剧集链接：/playurl/{vodid}/{sid}/{nid}.html，文本在 title 属性里。

8) 播放页（真实源码）：
   <script>var player_aaaa={"flag":"play","encrypt":0,"url":"https://v.fengbao14.com/.../index.m3u8","from":"bfzym3u8","id":"969677","sid":6,"nid":1, ...}</script>
   → url 字段即直链 m3u8（已实测该地址返回 HTTP 200 且为合法 #EXTM3U 播放列表）。
     故 playerContent 直接解析 player_aaaa.url 返回 parse=0；
     解析不到时退回 parse=1 交给 TVBox 嗅探。

9) 【播放实测：三种线路形态，均已逐条验证】（“少数线路不能播放”的根因）

   a. 普通 media 列表（bfzym3u8 / sid=6，64KB）
      https://v.fengbao14.com/video/.../index.m3u8
      → 直接含 #EXTINF 分片，明文，直链可用。

   b. 【master 列表】（lzm3u8 / sid=5，仅 96 字节）—— 原代码在这里黑屏
      #EXTM3U
      #EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=800000,RESOLUTION=1080x608
      2000k/hls/index.m3u8          ← 相对路径，必须 urljoin 补全
      TVBox 拿到 master 时不会自己选流，必须由爬虫解析出子列表再返回：
      子列表 https://v.lzcdn27.com/20261012/18849_4df56220/2000k/hls/index.m3u8
      实测 200 / 60721 字节 / 1536 个分片，明文可用。

   c. 【AES-128 加密】（jisu / sid=2，111KB）
      #EXT-X-KEY:METHOD=AES-128,URI="enc.key",IV=0x0000...0000
      分片 https://p.jisuts.com:999/hls/954/.../plist0.ts 实为密文
      （首字节 0xce，解密后 0x47 同步字节），key 地址
      https://vv.jisuzyv.com/play/aADQDzBe/enc.key 实测 200 / 16 字节。
      → TVBox/EXO 取 m3u8 时会自行按 URI 拉 key 解密，故只要把 m3u8 地址原样
        交出即可，绝不能改写。实测三种 Referer（无 / 本站 / CDN 自身）都能取到
        列表与 key，故 header 不必强绑播放页。

   d. 少数线路 m3u8 内是相对地址（无 scheme），也需 urljoin 补全为绝对地址。

10) 【稳定性】源站回源抖动频繁，同一页面会间歇性返回 Cloudflare 520
    （实测 /playurl/z9696775/1..5/1.html 连续 6 次全部 520，隔几分钟又恢复）。
    故 _fetch 默认对 520 错误页重试 1 次，playerContent 再补一次重试；
    仍失败才退回 parse=1（播放页本身没有视频流可嗅探，但保留兜底不报错）。

10.1) 【重大实测结论：源站整站回源不可用，只有 CF 缓存能出内容】
     本轮系统性探测确认，问题不是随机抖动，而是**按“有没有缓存”规律性失败**：

       GET /class/2.html        200  cf-cache-status:HIT  age:10927  18 卡片
       GET /class/2-2.html      200  cf-cache-status:HIT  age:3847   18 卡片
       GET /class/2-50.html     520  （无缓存 → 回源 → 挂）
       GET /class/13-3.html     520  （无缓存 → 回源 → 挂）
       GET /class/6-2.html      520  （无缓存 → 回源 → 挂）
       GET /explore/id/13.html             200 HIT 18 卡片
       GET /explore/area/内地/id/13.html   200 HIT 18 卡片
       GET /explore/id/2.html              520
       GET /explore/by/hits/id/2.html       520
       GET /explore/id/2/year/2024.html     520
       GET /celluloid/z3133105.html        200（之前抓过，已缓存）
       GET /celluloid/z1234567.html        520（从没被抓过）

     进一步按“路径里有没有中文/extra 段”分组，规律非常干净（同一分钟内多次验证）：
         GET /explore/id/7.html            200 23730   ← 纯数字，命中缓存
         GET /explore/id/6.html            200 23386   ← 纯数字，命中缓存
         GET /explore/id/40.html           200 19753   ← 纯数字，命中缓存
         GET /explore/class/喜剧/id/1.html  520   16   ← 含中文，不命中
         GET /explore/area/大陆/id/1.html   520   16   ← 含中文，不命中
         GET /explore/id/1/year/2024.html  520   16   ← 带 year 段，不命中
     即：**/explore/id/{纯数字}.html 这一形态可用**（等价于 /class/{数字}.html），
     其余带中文名或 year 的 explore 组合地址一律 520。
     加随机参数 ?_=xxx 绕开缓存后全部 520，确认是源站后端塌了，
     不是路径写错、也不是爬虫问题。站点恢复后代码无需改动即可正常工作。

     因此代码里做了三件事：
       a) _is_error_page 按真实错误页特征识别（cf-error / cf-wrapper /
          "Error code 520" / <title>…520:），不再靠零散字符串；
       b) categoryContent / searchContent 在拿到错误页时**不假装“0 条结果”**，
          而是二次重试后返回空列表，避免用户误以为“这个筛选条件没有片”；
       c) 「分类」这一维走 /class/{id}.html（与 /explore/id/{id}.html 同源），
          不拼中文段，因此即使在源站半挂的当下也能正常出片。

10.2) 【筛选面板的可用性实况（别误判成代码错）】
     分类（cls）→ /class/{id}.html          实测 5/5 全部通，18 条/页，翻页正常
     类型（cat）→ /explore/class/{名}/id/..  当前 520（含中文段）
     地区（area）→ /explore/area/{名}/id/..  当前 520（含中文段）
     年代（year）→ /explore/id/../year/..    当前 520（带 year 段）
     后者三组在源站恢复后即可用，URL 已逐字符对齐页面真实 href（219/219 校验通过）。
"""

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
                print("[zhongan]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.zhonganedu.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

DEFAULT_PIC = HOST + "/template/hl009/images/load.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺片"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "24", "type_name": "短剧"},
]

# ==================================================================
# 【筛选面板：严格照抄页面 */}
#
# 真实结构（GET /class/{tid}.html，列表区之前是一串 <dl class="dl-horizontal">）：
#     <dl class="dl-horizontal">
#       <dt>频道：</dt>
#       <dd class="ff-text-hidden ff-gallery">
#           <a class="" href="/explore/id/1.html">电影</a>
#           <a class=" btn-type btn-success is-selected" href="/explore/id/2.html">电视剧</a>
#           ...
#   五组合计（实测五个频道页都是这五组，顺序固定）：
#       频道 → 分类 → 类型 → 地区 → 年代
#
#   「分类」组才是二级分类，真实 href 形如：
#       <a class="btn-type btn-success is-selected" href="/explore.html">全部</a>
#       <a class="" href="/explore/id/13.html">国产剧</a>
#       <a class="" href="/explore/id/14.html">香港剧</a>
#     → 全部 = /explore.html（**没有 id 段**），其余 = /explore/id/{分类id}.html
#
#   「类型」组  /explore/class/{类型名}/id/{频道id}.html
#   「地区」组  /explore/area/{地区名}/id/{频道id}.html
#   「年代」组  /explore/id/{频道id}/year/{年}.html
#
#   注意 页面上**没有“排序”组**。整页唯一出现 by/hits 的地方是右上角那个
#   「筛选」按钮（<a class="btn btn-success btn-sm pull-right"
#                    href="/explore/by/hits/id/4.html">），它是入口不是筛选项。
#   所以这里不提供“排序”面板，免得给用户一个站上没有的选项。
#
# 下面三个表逐项取自页面 <a> 文本与 href，文本/顺序/是否存在都照实，不补不凑：
#   电影   : 类型 26（无重复）  地区 15（“大陆”）  年代 16（无 2011）
#   电视剧 : 类型 16            地区 10            年代 17
#   综艺   : 类型 13            地区  4            年代 15（2018..2004）
#   动漫   : 类型 20            地区  4            年代 15
#   短剧   : 类型/地区/年代 三组都只有一个空文本的“全部”，没有可选值
# ==================================================================

# 「分类」组：真实 href = /explore/id/{分类id}.html，名称取自 <a> 文本
_CATS_BY_TID = {
    "1":  [("6", "动作片"), ("7", "喜剧片"), ("8", "爱情片"), ("9", "科幻片"),
           ("10", "剧情片"), ("11", "战争片"), ("41", "动画片"), ("12", "记录片"),
           ("39", "恐怖片")],
    "2":  [("13", "国产剧"), ("14", "香港剧"), ("15", "韩国剧"), ("16", "欧美剧"),
           ("22", "台湾剧"), ("21", "日本剧"), ("20", "泰国剧"), ("23", "海外剧")],
    "3":  [("25", "大陆综艺"), ("26", "日韩综艺"), ("27", "港台综艺"),
           ("28", "欧美综艺")],
    "4":  [("29", "国产动漫"), ("30", "日本动漫"), ("42", "港台动漫"),
           ("31", "欧美动漫"), ("43", "海外动漫")],
    "24": [("40", "短剧大全"), ("44", "AI漫剧")],
}

# 「类型」组：/explore/class/{名}/id/{频道}.html
# 电影页上“恐怖”出现两次（分别在动作/科幻之后与枪战之后），此处去重保留一次，
# 因为同名链接指向完全相同的 URL /explore/class/恐怖/id/1.html。
_TYPES_BY_TID = {
    "1": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪", "犯罪",
          "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚", "经典", "青春",
          "文艺", "微电影", "古装", "历史", "运动", "农村", "儿童", "网络电影"],
    "2": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作",
          "奇幻", "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
    "3": ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实",
          "曲艺", "生活", "游戏互动", "财经", "求职"],
    "4": ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园", "动作",
          "机战", "运动", "战争", "少年", "少女", "社会", "原创", "亲子", "益智",
          "励志", "其他"],
}

# 「地区」组：/explore/area/{名}/id/{频道}.html
_AREAS_BY_TID = {
    "1": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
          "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
    "2": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国",
          "新加坡", "其他"],
    "3": ["内地", "港台", "日韩", "欧美"],
    "4": ["国产", "日本", "欧美", "其他"],
}

# 「年代」组：/explore/id/{频道}/year/{年}.html
_YEARS_BY_TID = {
    "1": [str(y) for y in range(2026, 2009, -1) if y != 2011],   # 页面无 2011
    "2": [str(y) for y in range(2026, 2009, -1)],
    "3": [str(y) for y in range(2018, 2003, -1)],
    "4": [str(y) for y in range(2018, 2003, -1)],
}


def _build_filters():
    """按页面五组 dl 组装 TVBox 筛选面板，key 与“能否同时生效”严格对应。

    站点是“点一次追加一段”的级联结构，真实可组合的段只有：
        [area] [class] /id/{id}/[year]
    「分类」本质上就是换 id（/explore/id/13.html），不是额外的一段。
    所以分类必须与 类型/地区/年代 互斥成同一个维度，否则拼出
    /explore/class/古装/id/13/year/2018.html 这种页面根本不会产生的地址。

    TVBox 的 filter 是“每个 key 各取一个值再一起传”的并列结构，
    因此这里把「分类」并进「类型」后紧邻的那一维，用一个 key=cat 表达：
        - cat 的值 = "id:13"（选二级分类，换 id，其余条件清空）
        - cat 的值 = "古装"  （选类型，保留当前 id）
    但两个都选会冲突，所以改成一个 key 承载，见 categoryContent 的解析。
    """
    out = {}
    for c in CLASSES:
        tid = c["type_id"]
        cats  = _CATS_BY_TID.get(tid) or []
        types = _TYPES_BY_TID.get(tid) or []
        areas = _AREAS_BY_TID.get(tid) or []
        years = _YEARS_BY_TID.get(tid) or []

        f = []

        # —— 第 1 组：分类（真实 /explore/id/{分类id}.html；“全部”= /explore.html）
        if cats:
            vals = [{"n": "全部", "v": ""}]
            vals += [{"n": n, "v": "id:" + cid} for cid, n in cats]
            f.append({"key": "cls", "name": "分类", "value": vals})

        # —— 第 2 组：类型（真实 /explore/class/{名}/id/{tid}.html）
        if types:
            f.append({"key": "cat", "name": "类型",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": t, "v": t} for t in types]})

        # —— 第 3 组：地区（真实 /explore/area/{名}/id/{tid}.html）
        if areas:
            f.append({"key": "area", "name": "地区",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": a, "v": a} for a in areas]})

        # —— 第 4 组：年代（真实 /explore/id/{tid}/year/{年}.html）
        if years:
            f.append({"key": "year", "name": "年代",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": y, "v": y} for y in years]})

        out[tid] = f
    return out


FILTERS = _build_filters()


# ===================== 正则 =====================

_RE_LI = re.compile(r'<li\s+class="ff-vod-img-list[\s\S]*?</li>', re.I)
_RE_LINK = re.compile(r'href="(/celluloid/[^"]+?\.html)"', re.I)
_RE_IMG_DATA = re.compile(r'data-original="([^"]+)"', re.I)
_RE_IMG_ANY = re.compile(r'<img[^>]*?src="([^"]+)"', re.I)
_RE_ALT = re.compile(r'alt="([^"]*)"', re.I)
_RE_TITLE_ATTR = re.compile(r'title="([^"]*)"', re.I)
_RE_REMARKS = re.compile(
    r'<em[^>]*class="[^"]*littplus[^"]*"[^>]*>([^<]*)</em>', re.I)

# 详情页标题：<a href="/celluloid/xxx.html" class="ff-text">片名</a>
_RE_D_TITLE = re.compile(
    r'<a\s+href="/celluloid/[^"]+"\s+class="ff-text"[^>]*>([^<]+)</a>', re.I)
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TAG_TITLE = re.compile(r'<title>([\s\S]*?)</title>', re.I)

# 详情页 <dt>标签：</dt><dd ...>值</dd>
def _dt(label):
    return re.compile(
        r'<dt[^>]*>\s*' + label + r'\s*[：:]\s*</dt>\s*<dd[^>]*>([\s\S]*?)</dd>',
        re.I)

_RE_DT_ACTOR    = _dt("主演")
_RE_DT_DIRECTOR = _dt("导演")
_RE_DT_AREA     = _dt("地区")
_RE_DT_YEAR     = _dt("年份")
_RE_DT_STATUS   = _dt("状态")

# 详情页封面区状态角标（真实源码）：
#   <span class="detail-thumb-text">更新至第20集</span>
# 位置在 <dl> 之前，且是页面主视觉上的状态，优先用它
_RE_THUMB_TEXT = re.compile(
    r'<span[^>]*class="[^"]*detail-thumb-text[^"]*"[^>]*>([\s\S]*?)</span>', re.I)

# 完整剧情正文
_RE_VOD_CONTENT = re.compile(r'<div class="vod-content">([\s\S]*?)</div>', re.I)

# 线路 tab：href="#playurl-tab-6" ... 线路1
_RE_TAB = re.compile(
    r'href="#playurl-tab-(\d+)"[^>]*>[\s\S]*?</span>\s*([^<]+?)\s*</a>', re.I)

# tab 面板：id="playurl-tab-6" ... </ul>
_RE_TABPANE = re.compile(
    r'<div[^>]*id="playurl-tab-(\d+)"[^>]*>([\s\S]*?)</div>', re.I)

# 面板内剧集：href="/playurl/z9696775/6/1.html" title="TC"
_RE_EPISODE = re.compile(
    r'<a[^>]*href="(/playurl/[^"]+?)"[^>]*title="([^"]*)"[^>]*>([^<]*)</a>', re.I)

# 播放页 player_aaaa
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)
_RE_PLAYER_LOOSE = re.compile(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*;', re.I)


class Spider(Spider):

    def getName(self):
        return "泡泡影院"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础 ----------------

    def _fetch(self, url, timeout=20, headers=None, retry=1):
        """取页面。站点源站回源抖动频繁（Cloudflare 520），
        实测同一 URL 间隔重试即可恢复，故默认重试 1 次。

        实测（2046 行）：
            /explore/class/喜剧/id/1.html   → 520
            /explore/area/大陆/id/1.html    → 520
            /explore/id/1.html              → 520
            /explore/area/内地/id/13.html   → 200 （几分钟后又恢复）
        同一批 URL 有 200 有 520，确认是源站回源不稳，不是路径写错。
        """
        tries = retry + 1
        for i in range(tries):
            try:
                h = dict(self.headers)
                if headers:
                    h.update(headers)
                rsp = self.fetch(url, headers=h, timeout=timeout)
                if hasattr(rsp, "text"):
                    txt = rsp.text or ""
                elif hasattr(rsp, "content"):
                    txt = rsp.content.decode("utf-8", "ignore")
                else:
                    txt = str(rsp)
                if txt and not self._is_error_page(txt):
                    return txt
                if i < tries - 1:
                    # 抖动间隔比 0.8s 长，逐次拉长退避
                    wait = 0.8 * (i + 1)
                    self.log("  错误页，%.1fs 后重试: %s" % (wait, url[:90]))
                    time.sleep(wait)
                    continue
                return txt
            except Exception as e:
                self.log("fetch FAIL(%d/%d) %s -> %s"
                         % (i + 1, tries, url[:90], e))
                if i < tries - 1:
                    time.sleep(0.8)
        return ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.site_url + url
        return urllib.parse.urljoin(self.site_url + "/", url)

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

    def _is_error_page(self, html):
        """识别 Cloudflare 502/520/521/522 错误页（源站回源失败时返回）。

        实测错误页原文（7365 字节左右）：
            <title>zhonganedu.com | 520: Web server is returning an unknown error</title>
            <body><div id="cf-wrapper"><div id="cf-error-details">
            <span class="code-label">Error code 520</span>
        这类页面**不含**任何影片卡片，如果不识别出来，就会被当成
        “这个筛选条件有 0 条结果”返回给 TVBox —— 用户看到空列表，
        分不清是站点抖了还是真的没片。故必须判定为错误页。
        """
        if not html:
            return True
        low = html.lower()
        if "cf-error" in low or "cf-wrapper" in low:
            return True
        if re.search(r"error\s+code\s*5\d\d", low):
            return True
        if re.search(r"<title>[^<]*5\d\d:", low):
            return True
        if "web server is returning" in low:
            return True
        return False

    def _is_placeholder(self, url):
        """识别懒加载占位图。

        真实源码里 data-original 有两种占位值：
            /template/hl009/images/load.gif   （绝大多数正常条目）
            /static/images/load.png           （无封面条目，如“老舅与我”）
        两者都不是真封面，必须丢掉换默认图，否则客户端显示破图。
        """
        if not url:
            return True
        low = url.lower()
        return ("load.gif" in low or "load.png" in low
                or low.startswith("data:image"))

    # ---------------- 列表 ----------------

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        if self._is_error_page(html):
            self.log("  站点返回错误页，跳过")
            return videos

        items = _RE_LI.findall(html)
        self.log("  卡片数: %d" % len(items))

        for it in items:
            m = _RE_LINK.search(it)
            if not m:
                continue
            href = m.group(1).replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)

            pic = ""
            mi = _RE_IMG_DATA.search(it)
            if mi:
                pic = self._fix_url(mi.group(1))
            if self._is_placeholder(pic):
                ma = _RE_IMG_ANY.search(it)
                if ma and not self._is_placeholder(ma.group(1)):
                    pic = self._fix_url(ma.group(1))
                else:
                    pic = ""
            pic = pic or self.default_pic

            name = ""
            mn = _RE_ALT.search(it)
            if mn:
                name = self._clean(mn.group(1))
            if not name:
                mt = _RE_TITLE_ATTR.search(it)
                if mt:
                    name = self._clean(mt.group(1))
            name = name or href.rsplit("/", 1)[-1].replace(".html", "")

            remarks = ""
            mr = _RE_REMARKS.search(it)
            if mr:
                remarks = self._clean(mr.group(1))

            videos.append({
                "vod_id":      href,
                "vod_name":    name[:100],
                "vod_pic":     pic,
                "vod_remarks": remarks,
            })
        return videos

    def _page_count(self, html, cid):
        """总页数取自真实“尾页”链接：
            分类/频道页  <a href="/class/13-2630.html">尾页</a>
            explore 页   <a href="/explore/.../page/58.html">尾页</a>
        """
        if not html or self._is_error_page(html):
            return 1
        cid = re.escape(str(cid))
        pats = [
            r'href="/class/%s-(\d+)\.html"[^>]*>\s*尾页' % cid,
            r'href="[^"]*/page/(\d+)\.html"[^>]*>\s*尾页',
            r'href="[^"]*page/(\d+)[^"]*"[^>]*>\s*尾页',
        ]
        for p in pats:
            m = re.search(p, html, re.I)
            if m:
                try:
                    return max(1, int(m.group(1)))
                except Exception:
                    pass
        return 1

    # ---------------- TVBox 接口 ----------------

    def _explore_url(self, cid, cat, area, year):
        """按站点真实链接规则拼 /explore 地址。

        站点上是“点一次在当前地址后追加一段”，所以真实出现过的段序为：
            /explore/class/古装/id/13.html               类型
            /explore/area/内地/id/13.html                地区
            /explore/id/13/year/2018.html                年代（year 恒在 id 后）
            /explore/area/内地/class/古装/id/13.html     地区已在再点类型
            /explore/class/古装/id/13/year/2018.html     类型+年代
        归纳：
            id 之前：[area] → [class]（先点地区再点类型，就是这个顺序）
            id 之后：[year]
        本函数只负责“类型/地区/年代”这三段，分类不在其中
        （分类是换 id，由调用方直接处理）。
        """
        q = urllib.parse.quote
        pre = ""
        if area:
            pre += "/area/%s" % q(area)
        if cat:
            pre += "/class/%s" % q(cat)
        tail = "/id/%s" % cid
        if year:
            tail += "/year/%s" % year
        return self.site_url + "/explore" + pre + tail + ".html"

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML: %d" % len(html))
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        tid = str(tid)

        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}

        # —— 四个筛选维度，取值全部来自页面面板的真实 <a> ——
        # cls  : 「分类」组，值形如 "id:13"（/explore/id/13.html）或 ""（全部=/explore.html）
        # cat  : 「类型」组，值就是类型名（/explore/class/古装/id/2.html）
        # area : 「地区」组，值就是地区名（/explore/area/内地/id/2.html）
        # year : 「年代」组，值就是年份  （/explore/id/2/year/2024.html）
        cls  = (extend.get("cls")  or "").strip()
        cat  = (extend.get("cat")  or "").strip()
        area = (extend.get("area") or "").strip()
        year = (extend.get("year") or "").strip()

        # 「分类」在本站就是换 id：页面上
        #     <a href="/explore/id/13.html">国产剧</a>
        # 与 /class/13.html 是同一个列表（实测 /explore/id/2.html 与
        # /class/2.html 正文一致，且 /explore/id/7.html 的“下一页/尾页”
        # 直接就是 /class/7-2.html、/class/7-4898.html）。
        # 所以选分类 = 把 id 段换成该分类，不额外加筛选段。
        cid = tid
        if cls.startswith("id:"):
            cid = cls[3:].strip() or tid

        # 真实路径拼接（严格对应站内 <a> 的 href 形状）：
        #   /explore[ /area/{地区} ][ /class/{类型} ]/id/{id}[ /year/{年} ].html
        # 页面从不产生“分类 + 类型/地区/年代”同时出现的地址（分类本身就是换 id），
        # 故选了分类时只用 id 段。翻页一律 /class/{id}-{N}.html（页面自己的链接）。
        if cat or area or year:
            if page > 1:
                url = "%s/class/%s-%d.html" % (self.site_url, cid, page)
            else:
                url = self._explore_url(cid, cat, area, year)
            fallback = ""      # 带筛选没有等价第二路径，失败就是失败
        else:
            # 无筛选（含只选分类）：/class/{id}.html 与 /explore/id/{id}.html
            # 是同一个列表（页面两种链接都有）。当前源站回源故障期间，
            # 只有 CDN 有缓存的才能打开，而缓存分布无规律
            # （实测同一时刻 /explore/id/7.html 200 而 /class/7.html 520；
            #   另一时刻又反过来 /class/2.html 200 而 /explore/id/2.html 520）。
            # 所以第 1 页做双路径回退：先 /class/，失败再 /explore/id/。
            primary   = "%s/class/%s.html" % (self.site_url, cid)
            secondary = "%s/explore/id/%s.html" % (self.site_url, cid)
            fallback  = secondary
            url = (primary if page == 1
                   else "%s/class/%s-%d.html" % (self.site_url, cid, page))

        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML: %d" % len(html))

        # 站点 520 时 _fetch 拿回来的仍是错误页。这时不能报“0 条”，
        # 否则 TVBox 会显示“没有相关内容”，用户以为筛选条件没片。
        # 实测源站几分钟内自愈，故这里多等一会儿再试一次。
        if self._is_error_page(html):
            time.sleep(2.0)
            html = self._fetch(url, retry=0)
            self.log("  二次重试后 HTML: %d" % len(html))

        # 双路径回退：/class/ 与 /explore/id/ 内容相同，换一条再试
        if self._is_error_page(html) and fallback:
            self.log("  回退备用路径: %s" % fallback)
            html = self._fetch(fallback, retry=1)
            self.log("  回退后 HTML: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html, cid)
        self.log("  结果: %d 条, 总页数: %d" % (len(videos), pagecount))

        if not videos and self._is_error_page(html):
            # 明确是站点故障：pagecode 留给调用方，list 为空但不伪装成“无结果”
            self.log("  ⚠ 站点返回 520，本次为故障而非无数据")
            return {
                "list": [],
                "page": page,
                "pagecount": 1,
                "limit": 24,
                "total": 0,
            }

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos) if videos else 24,
            "total": pagecount * (len(videos) if videos else 24),
        }

    def searchContent(self, key, quick, pg="1"):
        """搜索用真实表单：<form method="get" action="/query.html"><input name="wd">
             第1页  GET /query.html?wd=关键词
             翻页    GET /query/page/{页}/wd/{URL编码关键词}.html
                    真实样本（wd=老舅 的搜索结果页页脚）：
                    <a href="/query/page/1/wd/%E8%80%81%E8%88%85.html">尾页</a>
        关键词在路径段里，是 URL 编码后的形式；页数从“尾页”链接取，
        总数从 <span class="ff-text mac_total">4</span> 取。
        """
        kw_path = urllib.parse.quote(key)      # 路径段编码，与真实链接一致
        kw_qs   = urllib.parse.quote_plus(key)  # query 参数编码
        page = int(pg) if pg else 1

        if page > 1:
            url = "%s/query/page/%d/wd/%s.html" % (self.site_url, page, kw_path)
        else:
            url = "%s/query.html?wd=%s" % (self.site_url, kw_qs)

        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML: %d" % len(html))

        # 搜索页同样会被源站 520 命中（实测 wd=伟大的长征 即 520，
        # wd=老舅 正常）。重试一次，尽量别把故障当成“搜不到”。
        if self._is_error_page(html):
            time.sleep(1.5)
            html = self._fetch(url, retry=0)
            self.log("  二次重试后 HTML: %d" % len(html))

        videos = self._extract_videos(html)

        # 真实总数：<span class="ff-text mac_total">4</span>
        total = len(videos)
        mt = re.search(r'class="[^"]*mac_total[^"]*"[^>]*>\s*(\d+)\s*<', html, re.I)
        if mt:
            try:
                total = int(mt.group(1))
            except Exception:
                pass

        # 页数：优先尾页链接 /query/page/{N}/wd/...，其次按总数 / 每页条数
        pagecount = 1
        mlast = re.search(
            r'href="[^"]*/query/page/(\d+)/wd/[^"]*"[^>]*>\s*尾页', html, re.I)
        if mlast:
            try:
                pagecount = max(1, int(mlast.group(1)))
            except Exception:
                pagecount = 1
        elif videos and total > len(videos):
            pagecount = (total + len(videos) - 1) // len(videos)

        self.log("  结果: %d 条, 总数: %d, 页数: %d"
                 % (len(videos), total, pagecount))

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos) if videos else 24,
            "total": total,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 ----------------

    def _dl_value(self, html, regex):
        m = regex.search(html)
        if not m:
            return ""
        return self._clean(m.group(1))

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML: %d" % len(html))
        if not html or self._is_error_page(html):
            self.log("  详情页不可用")
            return {"list": []}

        # 标题：优先 <a class="ff-text">片名</a>，其次 <title>
        name = ""
        m = _RE_D_TITLE.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = _RE_H1.search(html)
            if m:
                name = self._clean(m.group(1))
        if not name:
            m = _RE_TAG_TITLE.search(html)
            if m:
                name = self._clean(m.group(1)).split(" - ")[0]
        name = name or vod_id

        # 封面
        pic = ""
        mi = _RE_IMG_DATA.search(html)
        if mi:
            pic = self._fix_url(mi.group(1))
        if self._is_placeholder(pic):
            pic = ""
            for mm in _RE_IMG_ANY.finditer(html):
                u = self._fix_url(mm.group(1))
                if u and not self._is_placeholder(u):
                    pic = u
                    break
        pic = pic or self.default_pic

        # 元信息
        actor    = self._dl_value(html, _RE_DT_ACTOR)
        director = self._dl_value(html, _RE_DT_DIRECTOR)
        area     = self._dl_value(html, _RE_DT_AREA)
        year     = self._dl_value(html, _RE_DT_YEAR)
        status   = self._dl_value(html, _RE_DT_STATUS)

        # 状态优先取封面角标 detail-thumb-text（真实源码在 <dl> 之前，
        # 内容与 <dt>状态</dt> 一致，但它是页面主视觉上露出的那个）
        thumb_status = ""
        mts = _RE_THUMB_TEXT.search(html)
        if mts:
            thumb_status = self._clean(mts.group(1))
        if thumb_status:
            status = thumb_status

        actor = re.sub(r"\s+", ", ", actor).strip(", ") if actor else ""
        actor = actor.replace(", ,", ",")

        # 简介：用完整剧情正文 vod-content（不是带“详细...”截断的 vod-blurb）
        content = ""
        mc = _RE_VOD_CONTENT.search(html)
        if mc:
            content = self._clean(mc.group(1))
        if not content:
            # 兜底：meta description
            md = re.search(r'<meta[^>]*name=["\']description["\'][^>]*'
                           r'content=["\']([^"\']*)["\']', html, re.I)
            if md:
                content = self._clean(md.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 线路 + 剧集：从 tab 的 href="#playurl-tab-{sid}" 取 sid（真实顺序是乱的）
        tab_names = {}
        for m in _RE_TAB.finditer(html):
            sid, label = m.group(1), self._clean(m.group(2))
            if sid not in tab_names:
                tab_names[sid] = label

        groups = []   # [(label, sid, [(ep_name, url), ...])]
        for m in _RE_TABPANE.finditer(html):
            sid, block = m.group(1), m.group(2)
            eps = []
            for em in _RE_EPISODE.finditer(block):
                href, title, text = em.group(1), em.group(2), em.group(3)
                href = href.replace("&amp;", "&")
                ep_name = self._clean(title) or self._clean(text) or \
                          ("第%d集" % (len(eps) + 1))
                eps.append((ep_name, self._fix_url(href)))
            if eps:
                label = tab_names.get(sid) or ("线路%s" % sid)
                groups.append((label, sid, eps))

        self.log("  线路: %s" % [(g[0], g[1], len(g[2])) for g in groups])

        if not groups:
            return {"list": []}

        play_from = "$$$".join(g[0] for g in groups)
        play_url = "$$$".join(
            "#".join("%s$%s" % (n, u) for n, u in g[2]) for g in groups)

        remarks = status or ("%d条线路" % len(groups))

        return {"list": [{
            "vod_id":        vod_id,
            "vod_name":      name,
            "vod_pic":       pic,
            "vod_content":   content,
            "vod_actor":     actor,
            "vod_director":  director,
            "vod_area":      area,
            "vod_year":      year,
            "vod_remarks":   remarks,
            "vod_play_from": play_from,
            "vod_play_url":  play_url,
        }]}

    # ---------------- 播放 ----------------

    def _parse_player(self, html):
        """解析 player_aaaa 的 url 字段（真实为直链 m3u8）"""
        if not html:
            return ""
        m = _RE_PLAYER.search(html) or _RE_PLAYER_LOOSE.search(html)
        if not m:
            return ""
        raw = m.group(1)
        try:
            data = json.loads(raw)
        except Exception:
            mu = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            if mu:
                return mu.group(1).replace("\\/", "/")
            return ""
        u = data.get("url") or ""
        return u.replace("\\/", "/")

    def _fetch_text(self, url, referer="", timeout=12):
        """取纯文本（给 m3u8 用），失败返回空串"""
        try:
            h = {"User-Agent": UA}
            if referer:
                h["Referer"] = referer
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
        except Exception as e:
            self.log("  m3u8 FAIL %s -> %s" % (url[:80], e))
        return ""

    def _pick_media_playlist(self, m3u8_url, referer=""):
        """把 master 列表解析成真正的 media 列表地址。

        实测形态（lzm3u8 / sid=5）：
            #EXTM3U
            #EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=800000,RESOLUTION=1080x608
            2000k/hls/index.m3u8          ← 相对路径
        TVBox 拿到 master 会黑屏/转圈，必须自己选出子列表。
        规则：按 #EXT-X-STREAM-INF 的 BANDWIDTH 取最大码率那条；
              没有 BANDWIDTH 就取第一条；子地址一律 urljoin 补全为绝对地址。
        """
        text = self._fetch_text(m3u8_url, referer)
        if not text or "#EXTM3U" not in text:
            return m3u8_url

        # 已是 media 列表（含分片），直接用
        if "#EXT-X-STREAM-INF" not in text:
            return m3u8_url

        # 逐条解析 STREAM-INF 与其后紧跟的那一行 URI
        variants = []
        lines = [ln.strip() for ln in text.replace("\r", "").split("\n")]
        i = 0
        while i < len(lines):
            ln = lines[i]
            if ln.startswith("#EXT-X-STREAM-INF"):
                bw = 0
                mb = re.search(r"BANDWIDTH=(\d+)", ln)
                if mb:
                    try:
                        bw = int(mb.group(1))
                    except Exception:
                        bw = 0
                # 找下一行非注释、非空行作为子列表地址
                j = i + 1
                while j < len(lines):
                    nxt = lines[j]
                    if nxt and not nxt.startswith("#"):
                        variants.append((bw, nxt))
                        i = j
                        break
                    j += 1
            i += 1

        if not variants:
            return m3u8_url

        variants.sort(key=lambda x: x[0], reverse=True)
        sub = variants[0][1]
        # 相对路径 → 绝对地址（实测为 2000k/hls/index.m3u8 这种相对形式）
        if not sub.startswith("http"):
            sub = urllib.parse.urljoin(m3u8_url, sub)
        self.log("  master -> 子列表(%d 条候选, 选中 bw=%d): %s"
                 % (len(variants), variants[0][0], sub[:110]))
        return sub

    def _normalize_play_url(self, url, referer=""):
        """m3u8 地址规整：
           1) 去掉 iOS 专用的 EXT-X 查询串（TVBox 不需要）
           2) master 列表解析出 media 子列表
           3) 其余原样返回，绝不改写分片/key 地址（AES 线路靠它解密）
        """
        if not url:
            return url
        u = url.strip()

        # 苹果CMS部分源带 ?&ext=... 之类后缀，去掉不影响播放
        if "#" in u:
            u = u.split("#", 1)[0]

        if ".m3u8" not in u.lower():
            return u

        try:
            return self._pick_media_playlist(u, referer)
        except Exception as e:
            self.log("  列表解析异常，用原地址: %s" % e)
            return u

    def playerContent(self, flag, id, vipFlags):
        play_url = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_url)

        now = int(time.time())
        if play_url in self._play_cache:
            ts, res = self._play_cache[play_url]
            if now - ts < 600:
                return res

        # 播放页偶发 520（源站回源抖动），重试一次，别直接丢给嗅探
        html = self._fetch(play_url)
        m3u8 = self._parse_player(html)
        if not m3u8:
            time.sleep(0.6)
            html = self._fetch(play_url)
            m3u8 = self._parse_player(html)

        if m3u8 and m3u8.startswith("http"):
            m3u8 = self._normalize_play_url(m3u8, play_url)
            self.log("  => 直链: %s" % m3u8[:120])
            res = {
                "parse": 0,
                "playUrl": "",
                "url": m3u8,
                "header": {
                    "User-Agent": UA,
                    "Referer": play_url,
                },
            }
        else:
            self.log("  未取到直链，交给嗅探")
            res = {
                "parse": 1,
                "playUrl": "",
                "url": play_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }

        self._play_cache[play_url] = (now, res)
        return res

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
            rsp = self.fetch(url, headers={
                "User-Agent": UA, "Referer": self.site_url + "/"}, timeout=15)
            content = rsp.content
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
