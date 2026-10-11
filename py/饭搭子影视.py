# -*- coding: utf-8 -*-
# ============ 饭搭子影视 源 (fdzys.com) 动态筛选完整版 ============
import sys, re, json
from urllib.parse import quote

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            import requests as rq
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

# ============ ★ 配置区 ============
HOST = 'https://fdzys.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
VIDEO_EXTS = 'm3u8|mp4|flv|mkv|avi|ts'

# 一级分类（仅保留导航栏显示的 6 个）
CATEGORIES = [
    {'type_id': 'movie',   'type_name': '电影'},
    {'type_id': 'tv',      'type_name': '电视剧'},
    {'type_id': 'dongman', 'type_name': '动漫片'},
    {'type_id': 'zongyi',  'type_name': '综艺片'},
    {'type_id': 'tiyu',    'type_name': '体育'},
    {'type_id': 'duanju',  'type_name': '短剧'},
]

# ============ ★ 筛选选项（根据网站实际筛选栏） ============
# 每个一级分类下的筛选维度
FILTER_OPTIONS = {
    'movie': {
        'class': [('dongzuo','动作'),('xiju','喜剧'),('aiqing','爱情'),('kehuan','科幻'),
                  ('kongbu','恐怖'),('juqing','剧情'),('zhanzheng','战争'),('fanzui','犯罪'),
                  ('xuanyi','悬疑'),('donghua','动画'),('jilu','纪录'),('guzhuang','古装')],
        'area':  [('dalu','大陆'),('xianggang','香港'),('taiwan','台湾'),('meiguo','美国'),
                  ('riben','日本'),('hanguo','韩国'),('yingguo','英国'),('faguo','法国')],
        'lang':  [('guoyu','国语'),('yingyu','英语'),('riyu','日语'),('hanyu','韩语'),('yueyu','粤语')],
        'year':  [(str(y), str(y)) for y in range(2026, 2017, -1)],
    },
    'tv': {
        'class': [('guochan','国产'),('oumei','欧美'),('riben','日本'),('hanguo','韩国'),
                  ('gangtai','港台'),('juqing','剧情'),('aiqing','爱情'),('xuanyi','悬疑')],
        'area':  [('dalu','大陆'),('xianggang','香港'),('taiwan','台湾'),('meiguo','美国'),
                  ('riben','日本'),('hanguo','韩国'),('yingguo','英国')],
        'lang':  [('guoyu','国语'),('yingyu','英语'),('riyu','日语'),('hanyu','韩语'),('yueyu','粤语')],
        'year':  [(str(y), str(y)) for y in range(2026, 2017, -1)],
    },
    'dongman': {
        'class': [('guochan','国漫'),('rihan','日韩'),('oumei','欧美'),('donghua','动画'),
                  ('juqing','剧情'),('kehuan','科幻'),('xuanhuan','玄幻')],
        'area':  [('dalu','大陆'),('riben','日本'),('meiguo','美国'),('hanguo','韩国')],
        'lang':  [('guoyu','国语'),('riyu','日语'),('yingyu','英语')],
        'year':  [(str(y), str(y)) for y in range(2026, 2017, -1)],
    },
    'zongyi': {
        'class': [('dalu','大陆'),('gangtai','港台'),('rihan','日韩'),('oumei','欧美'),
                  ('zongyi','综艺'),('yinyue','音乐'),('youxi','游戏')],
        'area':  [('dalu','大陆'),('xianggang','香港'),('taiwan','台湾'),('riben','日本'),('hanguo','韩国')],
        'lang':  [('guoyu','国语'),('yueyu','粤语'),('riyu','日语'),('hanyu','韩语')],
        'year':  [(str(y), str(y)) for y in range(2026, 2017, -1)],
    },
    'tiyu': {
        'class': [('zuqiu','足球'),('lanqiu','篮球'),('wangqiu','网球'),('taiqiu','斯诺克')],
        'area':  [('all','全部')],
        'lang':  [('guoyu','国语')],
        'year':  [],
    },
    'duanju': {
        'class': [('all','全部'),('aiqing','爱情'),('juqing','剧情'),('xuanhuan','玄幻')],
        'area':  [('all','全部')],
        'lang':  [('guoyu','国语')],
        'year':  [],
    },
}

# 排序选项
SORT_OPTIONS = [
    {'n': '默认', 'v': ''},
    {'n': '最热', 'v': 'hot'},
    {'n': '最新', 'v': 'new'},
    {'n': '评分', 'v': 'score'},
]

# 哪些分类支持筛选（体育和短剧不支持年份筛选）
FILTER_TYPES = ('movie', 'tv', 'dongman', 'zongyi')

class Spider(Spider):
    def init(self, extend=''):
        self.base = HOST.rstrip('/')
        self.ua = UA
        self.types = {c['type_id']: c['type_name'] for c in CATEGORIES}
        self._hd = {
            'User-Agent': self.ua,
            'Referer': self.base + '/',
            'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
        }

    # ========== 动态构建筛选菜单 ==========
    def _build_filters(self):
        fs = {}
        for c in CATEGORIES:
            tid = c['type_id']
            opts = FILTER_OPTIONS.get(tid, {})
            if not opts:
                continue
            filters = []
            # 剧情
            if opts.get('class'):
                filters.append({
                    'key': 'class', 'name': '剧情',
                    'value': [{'n': '全部', 'v': ''}] + [{'n': n, 'v': v} for v, n in opts['class']]
                })
            # 地区
            if opts.get('area'):
                filters.append({
                    'key': 'area', 'name': '地区',
                    'value': [{'n': '全部', 'v': ''}] + [{'n': n, 'v': v} for v, n in opts['area']]
                })
            # 语言
            if opts.get('lang'):
                filters.append({
                    'key': 'lang', 'name': '语言',
                    'value': [{'n': '全部', 'v': ''}] + [{'n': n, 'v': v} for v, n in opts['lang']]
                })
            # 年份（体育和短剧跳过）
            if opts.get('year') and tid in FILTER_TYPES:
                filters.append({
                    'key': 'year', 'name': '年份',
                    'value': [{'n': '全部', 'v': ''}] + [{'n': y, 'v': y} for y, _ in opts['year']]
                })
            # 排序
            filters.append({
                'key': 'sort', 'name': '排序',
                'value': SORT_OPTIONS
            })
            if filters:
                fs[tid] = filters
        return fs

    # ========== 请求工具 ==========
    def _get(self, url):
        try:
            r = self.fetch(url, headers=self._hd, timeout=15000)
            return r.text if hasattr(r, 'text') else str(r)
        except Exception:
            return ''

    def _abs(self, u):
        if not u: return ''
        if u.startswith('http'): return u
        if u.startswith('//'): return 'https:' + u
        return self.base + (u if u.startswith('/') else '/' + u)

    # ========== 列表卡片解析 ==========
    def _items(self, h):
        items, seen = [], set()
        if not h: return items
        cards = re.findall(
            r'<a\s+[^>]*href="([^"]+)"[^>]*>[\s\S]*?<img[^>]*(?:data-src|src)="([^"]+)"[^>]*>[\s\S]*?(?:<div class="title">|title=")([^"<]+)[^>]*>[\s\S]*?<div class="tag[^>]*>([^<]+)</div>',
            h)
        for url, pic, name, remark in cards:
            if not re.search(r'/(?:movie|tv|dongman|zongyi|tiyu|duanju)/', url):
                continue
            vid = self._abs(url)
            if vid in seen: continue
            seen.add(vid)
            name = name.strip()
            if not name: continue
            items.append({
                'vod_id': vid,
                'vod_name': name[:60],
                'vod_pic': self._abs(pic),
                'vod_remarks': remark.strip()[:30]
            })
        return items

    def _pagecount(self, h, cur):
        mx = cur
        for m in re.finditer(r'[?&]page=(\d+)', h):
            try: mx = max(mx, int(m.group(1)))
            except: pass
        if mx == cur and re.search(r'class="listitem|tab-pane', h):
            mx = cur + 1
        return mx

    # ========== TVBox 接口 ==========
    def homeContent(self, filter=False):
        r = {'class': [{'type_id': k, 'type_name': v} for k, v in self.types.items()]}
        if filter:
            r['filters'] = self._build_filters()
        r['list'] = self.homeVideoContent().get('list', [])
        return r

    def homeVideoContent(self):
        h = self._get(self.base)
        return {'list': self._items(h) if h else []}

    # ========== ★ 动态筛选分类（核心修改） ==========
    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        try: pn = max(int(str(pg)), 1)
        except: pn = 1

        ex = {}
        if extend:
            try: ex = json.loads(extend) if isinstance(extend, str) else dict(extend)
            except: ex = {}

        # 解析一级分类
        path = str(tid).strip('/')
        parts = path.split('/')
        main_cat = parts[0] if parts else path

        # ★ 动态拼接筛选参数
        # 格式：/{一级}/{二级-地区-语言-年份}/{排序}
        segments = []

        # 剧情/二级分类（必填，默认 all）
        cls = ex.get('class') or 'all'
        segments.append(cls)

        # 地区（可选）
        if ex.get('area'):
            segments.append(ex['area'])

        # 语言（可选）
        if ex.get('lang'):
            segments.append(ex['lang'])

        # 年份（可选，体育和短剧不拼）
        if ex.get('year') and main_cat in FILTER_TYPES:
            segments.append(ex['year'])

        # 如果所有可选参数都为空，只保留二级分类
        filter_path = '-'.join(segments)

        # 排序（可选）
        sort = ex.get('sort') or ''
        sort_suffix = '/' + sort if sort else ''

        # 拼接完整 URL
        url = '%s/%s/%s%s' % (self.base, main_cat, filter_path, sort_suffix)
        if pn > 1:
            url += '?page=%d' % pn

        h = self._get(url)
        if not h:
            return {'page': pn, 'pagecount': pn, 'limit': 24, 'total': 0, 'list': []}
        items = self._items(h)
        return {'page': pn, 'pagecount': self._pagecount(h, pn), 'limit': 24,
                'total': len(items), 'list': items}

    # ========== 详情页（修复简介与元数据） ==========
    def detailContent(self, ids, quick='1'):
        vid = str(ids[0] if isinstance(ids, list) else ids or '')
        h = self._get(self._abs(vid))
        if not h: return {'list': []}

        d = {'vod_id': vid, 'vod_name': '', 'vod_pic': '', 'vod_actor': '',
             'vod_content': '', 'vod_remarks': '', 'vod_play_from': '', 'vod_play_url': ''}

        # 标题
        m = re.search(r'<div class="info-title">([^<]+)</div>', h)
        if not m:
            m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', h)
        if m: d['vod_name'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 封面
        for pat in (r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
                    r'data-cover="([^"]+)"'):
            m = re.search(pat, h, re.I)
            if m: d['vod_pic'] = self._abs(m.group(1).strip()); break

        # 简介（真实剧情）
        m = re.search(r'<div class="info-intro">简介：([\s\S]*?)</div>', h)
        if m:
            intro = re.sub(r'<[^>]+>', '', m.group(1))
            d['vod_content'] = re.sub(r'\s+', ' ', intro).strip()

        # 演员
        m = re.search(r'<div class="info-roles">主演：([^<]+)</div>', h)
        if m: d['vod_actor'] = m.group(1).strip()

        # 状态
        m = re.search(r'<div class="tag[^>]*>([^<]+)</div>', h)
        if m: d['vod_remarks'] = m.group(1).strip()

        # 线路与选集
        routes = {}
        for sid, seg in re.findall(r'<li class="swiper-slide player_name[^"]*" data-sid="(\d+)">([\s\S]*?)</li>', h):
            name_match = re.search(r'<a[^>]*>([^<]+)<span', seg)
            if name_match:
                routes[sid] = name_match.group(1).strip()

        body = h.split('class="tab-content"', 1)[-1]
        blocks = re.split(r'<div id="playlist\d+" class="tab-pane[^"]*" data-sid="(\d+)">', body)

        groups = []
        seen_sid = set()
        for i in range(1, len(blocks), 2):
            sid = blocks[i]
            if sid in seen_sid: continue
            seen_sid.add(sid)
            seg = blocks[i + 1].split('<div id="playlist')[0]
            eps = re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', seg)
            if eps:
                groups.append((sid, eps))

        if groups:
            froms, urls = [], []
            for sid, eps in groups:
                froms.append(routes.get(sid, '线路' + sid))
                urls.append('#'.join('%s$%s' % (ep.strip().replace('#', '-'), self._abs(u)) for u, ep in eps))
            d['vod_play_from'] = '$$$'.join(froms)
            d['vod_play_url'] = '$$$'.join(urls)

        return {'list': [d]}

    # ========== 搜索 ==========
    def searchContent(self, key, quick=False, pg='1'):
        h = self._get('%s/yu-%s-xiangquan-de-yingpian-shippin-zhibo' % (self.base, quote(str(key))))
        return {'list': self._items(h) if h else []}

    # ========== 播放 ==========
    def playerContent(self, flag, id, vipFlags=None):
        url = str(id)
        if not url.startswith('http'): url = self._abs(url)
        if re.search(r'\.(?:%s)(?:\?|$)' % VIDEO_EXTS, url, re.I):
            return {'parse': 0, 'url': url, 'header': json.dumps(self._hd)}

        h = self._get(url)
        if not h: return {'parse': 0, 'url': ''}

        m = re.search(r'var player_aaaa=(\{.*?\})</script>', h)
        if not m: return {'parse': 0, 'url': ''}

        try: j = json.loads(m.group(1))
        except: return {'parse': 0, 'url': ''}

        share = (j.get('url') or '').strip()
        if not share: return {'parse': 0, 'url': ''}

        if re.search(r'\.(?:%s)(?:\?|$)' % VIDEO_EXTS, share, re.I):
            return {'parse': 0, 'url': share, 'header': json.dumps(self._hd)}

        if not share.startswith('http'):
            return {'parse': 1, 'url': share}

        h2 = self._get(share)
        m2 = re.search(r'const url\s*=\s*"([^"]+)"', h2 or '')
        if not m2:
            return {'parse': 0, 'url': share}

        path = m2.group(1)
        if path.startswith('http'):
            final = path
        elif path.startswith('/'):
            origin = re.match(r'https?://[^/]+', share)
            final = (origin.group(0) if origin else self.base) + path
        else:
            final = share.rsplit('/', 1)[0] + '/' + path

        return {'parse': 0, 'url': final, 'header': json.dumps(self._hd)}

    def isVideoFormat(self, url):
        if not url: return False
        return '.m3u8' in url or bool(re.search(r'\.(?:%s)(?:\?|$)' % VIDEO_EXTS, url, re.I))

    def manualVideoCheck(self): return False
    def destroy(self): pass
