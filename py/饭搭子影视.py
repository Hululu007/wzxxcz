# -*- coding: utf-8 -*-
# ============ 饭搭子影视 源 (fdzys.com) 完美修复版 ============
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

HOST = 'https://fdzys.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
VIDEO_EXTS = 'm3u8|mp4|flv|mkv|avi|ts'

CATEGORIES = [
    {'type_id': 'movie',   'type_name': '电影'},
    {'type_id': 'tv',      'type_name': '电视剧'},
    {'type_id': 'dongman', 'type_name': '动漫片'},
    {'type_id': 'zongyi',  'type_name': '综艺片'},
    {'type_id': 'tiyu',    'type_name': '体育'},
    {'type_id': 'duanju',  'type_name': '短剧'},
]

FILTER_OPTIONS = {
    'movie': {
        'class': [('dongzuo','动作'),('xiju','喜剧'),('aiqing','爱情'),('kehuan','科幻'),('kongbu','恐怖'),('juqing','剧情'),('zhanzheng','战争'),('fanzui','犯罪')],
        'area':  [('dalu','大陆'),('xianggang','香港'),('taiwan','台湾'),('meiguo','美国'),('riben','日本'),('hanguo','韩国')],
        'lang':  [('guoyu','国语'),('yingyu','英语'),('riyu','日语'),('hanyu','韩语'),('yueyu','粤语')],
        'year':  [(str(y), str(y)) for y in range(2026, 2017, -1)],
    },
    'tv': {
        'class': [('guochan','国产'),('oumei','欧美'),('riben','日本'),('hanguo','韩国'),('juqing','剧情'),('aiqing','爱情')],
        'area':  [('dalu','大陆'),('xianggang','香港'),('taiwan','台湾'),('meiguo','美国'),('riben','日本'),('hanguo','韩国')],
        'lang':  [('guoyu','国语'),('yingyu','英语'),('riyu','日语'),('hanyu','韩语'),('yueyu','粤语')],
        'year':  [(str(y), str(y)) for y in range(2026, 2017, -1)],
    },
    'dongman': {
        'class': [('guochan','国漫'),('rihan','日韩'),('oumei','欧美'),('donghua','动画')],
        'area':  [('dalu','大陆'),('riben','日本'),('meiguo','美国')],
        'lang':  [('guoyu','国语'),('riyu','日语')],
        'year':  [(str(y), str(y)) for y in range(2026, 2017, -1)],
    },
    'zongyi': {
        'class': [('dalu','大陆'),('gangtai','港台'),('rihan','日韩'),('oumei','欧美')],
        'area':  [('dalu','大陆'),('xianggang','香港'),('taiwan','台湾')],
        'lang':  [('guoyu','国语'),('yueyu','粤语')],
        'year':  [(str(y), str(y)) for y in range(2026, 2017, -1)],
    },
    'tiyu': {
        'class': [('zuqiu','足球'),('lanqiu','篮球'),('wangqiu','网球')],
        'area': [], 'lang': [], 'year': [],
    },
    'duanju': {
        'class': [('all','全部'),('aiqing','爱情'),('juqing','剧情')],
        'area': [], 'lang': [], 'year': [],
    },
}

SORT_OPTIONS = [{'n': '默认', 'v': ''}, {'n': '最热', 'v': 'hot'}, {'n': '最新', 'v': 'new'}]
FILTER_TYPES = ('movie', 'tv', 'dongman', 'zongyi')

class Spider(Spider):
    def init(self, extend=''):
        self.base = HOST.rstrip('/')
        self._hd = {'User-Agent': UA, 'Referer': self.base + '/'}

    def _build_filters(self):
        fs = {}
        for c in CATEGORIES:
            tid = c['type_id']
            opts = FILTER_OPTIONS.get(tid, {})
            if not opts: continue
            filters = []
            for key, name in [('class','剧情'), ('area','地区'), ('lang','语言'), ('year','年份')]:
                if opts.get(key):
                    filters.append({'key': key, 'name': name, 'value': [{'n': '全部', 'v': ''}] + [{'n': n, 'v': v} for v, n in opts[key]]})
            filters.append({'key': 'sort', 'name': '排序', 'value': SORT_OPTIONS})
            fs[tid] = filters
        return fs

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

    # ========== ★ 重写列表卡片解析（彻底修复没图片问题） ==========
    def _items(self, h):
        items, seen = [], set()
        if not h: return items
        
        # 1. 先宽松匹配所有可能包含影视链接的 a 标签
        for m in re.finditer(r'<a\s+[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', h):
            url = m.group(1)
            inner = m.group(2)
            full_tag = m.group(0)
            
            # 只保留包含具体分类路径的链接，过滤掉广告或导航
            if not re.search(r'/(?:movie|tv|dongman|zongyi|tiyu|duanju)/', url):
                continue
                
            vid = self._abs(url)
            if vid in seen: continue
            seen.add(vid)
            
            # 2. 提取图片：优先 data-src、data-original，过滤掉 loading 图
            pic = ''
            for p in re.finditer(r'<img[^>]*?(?:data-original|data-src|src)=["\']([^"\']+)["\']', inner):
                img_url = p.group(1)
                if 'base64' not in img_url and 'loading' not in img_url and '.gif' not in img_url:
                    pic = self._abs(img_url)
                    break
            
            # 3. 提取标题：优先 title 属性，其次 div.title
            name_m = re.search(r'title="([^"]+)"', full_tag)
            if not name_m:
                name_m = re.search(r'<div class="title">([^<]+)</div>', inner)
            name = name_m.group(1).strip() if name_m else ''
            if not name: continue
            
            # 4. 提取备注（如“全剧集”、“更新至第30集”）
            remark_m = re.search(r'<div class="tag[^>]*>([^<]+)</div>', inner)
            remark = remark_m.group(1).strip() if remark_m else ''
            
            items.append({
                'vod_id': vid,
                'vod_name': name[:60],
                'vod_pic': pic,
                'vod_remarks': remark[:30]
            })
        return items

    def _pagecount(self, h, cur):
        mx = cur
        for m in re.finditer(r'[?&]page=(\d+)', h):
            try: mx = max(mx, int(m.group(1)))
            except: pass
        return mx if mx > cur else cur + 1

    def homeContent(self, filter=False):
        r = {'class': [{'type_id': k, 'type_name': v} for k, v in {c['type_id']: c['type_name'] for c in CATEGORIES}.items()]}
        if filter: r['filters'] = self._build_filters()
        r['list'] = self.homeVideoContent().get('list', [])
        return r

    def homeVideoContent(self):
        return {'list': self._items(self._get(self.base))}

    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        try: pn = max(int(str(pg)), 1)
        except: pn = 1
        ex = json.loads(extend) if isinstance(extend, str) and extend else (extend if isinstance(extend, dict) else {})
        
        main_cat = str(tid).split('/')[0]
        segments = [ex.get('class') or 'all']
        if ex.get('area'): segments.append(ex['area'])
        if ex.get('lang'): segments.append(ex['lang'])
        if ex.get('year') and main_cat in FILTER_TYPES: segments.append(ex['year'])
        
        filter_path = '-'.join(segments)
        sort_suffix = '/' + ex['sort'] if ex.get('sort') else ''
        url = '%s/%s/%s%s' % (self.base, main_cat, filter_path, sort_suffix)
        if pn > 1: url += '?page=%d' % pn

        h = self._get(url)
        items = self._items(h)
        return {'page': pn, 'pagecount': self._pagecount(h, pn), 'limit': 24, 'total': len(items), 'list': items}

    # ========== ★ 重写详情页（彻底修复简介没取对问题） ==========
    def detailContent(self, ids, quick='1'):
        vid = str(ids[0] if isinstance(ids, list) else ids or '')
        h = self._get(self._abs(vid))
        if not h: return {'list': []}
        
        d = {'vod_id': vid, 'vod_name': '', 'vod_pic': '', 'vod_actor': '', 'vod_content': '', 'vod_remarks': '', 'vod_play_from': '', 'vod_play_url': ''}
        
        # 标题
        m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', h) or re.search(r'<div class="info-title">([^<]+)</div>', h)
        if m: d['vod_name'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        
        # 封面
        m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', h, re.I)
        if m: d['vod_pic'] = self._abs(m.group(1).strip())
        
        # ★ 简介修复：抓取 info-intro 内的所有文本
        m = re.search(r'<div class="info-intro">([\s\S]*?)</div>', h)
        if m:
            raw_intro = m.group(1)
            # 移除“简介：”字样和 HTML 标签
            raw_intro = re.sub(r'简介[:：]?', '', raw_intro)
            d['vod_content'] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', raw_intro)).strip()
        else:
            # 兜底方案：如果找不到 info-intro，尝试抓取 meta description
            m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', h)
            if m: d['vod_content'] = m.group(1).strip()
            
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
            if name_match: routes[sid] = name_match.group(1).strip()
            
        body = h.split('class="tab-content"', 1)[-1]
        blocks = re.split(r'<div id="playlist\d+" class="tab-pane[^"]*" data-sid="(\d+)">', body)
        
        groups, seen_sid = [], set()
        for i in range(1, len(blocks), 2):
            sid = blocks[i]
            if sid in seen_sid: continue
            seen_sid.add(sid)
            seg = blocks[i + 1].split('<div id="playlist')[0]
            eps = re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', seg)
            if eps: groups.append((sid, eps))
            
        if groups:
            froms, urls = [], []
            for sid, eps in groups:
                froms.append(routes.get(sid, '线路' + sid))
                urls.append('#'.join('%s$%s' % (ep.strip().replace('#', '-'), self._abs(u)) for u, ep in eps))
            d['vod_play_from'] = '$$$'.join(froms)
            d['vod_play_url'] = '$$$'.join(urls)
            
        return {'list': [d]}

    def searchContent(self, key, quick=False, pg='1'):
        h = self._get('%s/yu-%s-xiangquan-de-yingpian-shippin-zhibo' % (self.base, quote(str(key))))
        return {'list': self._items(h) if h else []}

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
        if not share.startswith('http'): return {'parse': 1, 'url': share}
        h2 = self._get(share)
        m2 = re.search(r'const url\s*=\s*"([^"]+)"', h2 or '')
        if not m2: return {'parse': 0, 'url': share}
        path = m2.group(1)
        final = path if path.startswith('http') else ((re.match(r'https?://[^/]+', share).group(0) if re.match(r'https?://[^/]+', share) else self.base) + path if path.startswith('/') else share.rsplit('/', 1)[0] + '/' + path)
        return {'parse': 0, 'url': final, 'header': json.dumps(self._hd)}

    def isVideoFormat(self, url): return bool(url) and ('.m3u8' in url or bool(re.search(r'\.(?:%s)(?:\?|$)' % VIDEO_EXTS, url, re.I)))
    def manualVideoCheck(self): return False
    def destroy(self): pass
