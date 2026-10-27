# -*- coding: utf-8 -*-
"""
电影侠 dyx00.com | TVBox Python 爬虫 
关键:
  -  _api_detail AES 接口 + _api_detail_html 兜底
  -  _build_split 分类桶 + _SPLIT_FILE 缓存
  - 播放多级兜底 (playSource / 裸 src / m3u8 / mp4)
"""
import sys
import os
import re
import json
import time
import hmac
import hashlib
import threading
import unicodedata
import urllib.parse
import requests

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class _BaseSpider:
        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                self._session = requests.Session()
                self._session.verify = False
                adapter = requests.adapters.HTTPAdapter(
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
                print("[dyx00]", *a)
            except Exception:
                pass

    Spider = _BaseSpider

# 抑制 InsecureRequestWarning
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass


# ===================== 常量 =====================
HOST = 'https://www.dyx00.com'
PIC_CDN = 'https://vres.cyscyy.com'
UA = ('Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36')

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

SKIP = ('搜索', '百度', '搜狗', '神马', '360', 'baidu', 'google',
        'sogou', 'kuaishou', '快手')
WM = ('kkys', 'kekys', '可可影视')

CLASSES = [
    {'type_name': '今日更新', 'type_id': 'new'},
    {'type_name': '电影', 'type_id': '1'},
    {'type_name': '连续剧', 'type_id': '2'},
    {'type_name': '动漫', 'type_id': '3'},
    {'type_name': '综艺纪录', 'type_id': '4'},
    {'type_name': '短剧', 'type_id': '6'},
]

FILTERS = {
    '1': [
        {'key': 'year', 'name': '年份',
         'value': [{'n': '全部', 'v': ''}, {'n': '2024', 'v': '2024'},
                   {'n': '2023', 'v': '2023'}, {'n': '2022', 'v': '2022'}]},
    ],
    '2': [
        {'key': 'year', 'name': '年份',
         'value': [{'n': '全部', 'v': ''}, {'n': '2024', 'v': '2024'},
                   {'n': '2023', 'v': '2023'}]},
    ],
}

# ===================== 缓存 / 全局 =====================
_CAT_CACHE = {}
_CAT_LOCK = threading.Lock()
_SESS = None
_SESS_LOCK = threading.Lock()
_CAT_FILE = '/sdcard/Download/电影侠_cat.json'
_SPLIT_FILE = '/sdcard/Download/电影侠_split.json'
_SPLIT_CACHE = None
_SPLIT_BUILDING = False
_SPLIT_LOCK = threading.Lock()

# ===================== vcache 加密参数 =====================
_VC = 'https://vcache.mjrlin.cn'
_VC_KEY = b'ayt5wy5afwmwrpb19k9s3psx3dymyd0n'
_VC_IV = b'b3t069ijy7pirw0j'
_VC_HASH = 'te@9fs#5tbf8#dx7zw8nx'
_VC_UA = ('com.kkdyC1V260805.T180309/3.5.0 Dalvik/2.1.0 '
          '(Linux; U; Android 11; KB2000 Build/RP1A.201005.001)')


# ===================== 正则 =====================
_RE_ITEM = re.compile(
    r'<a[^>]*href="(/detail/(\d+)\.html)"[^>]*class="v-item"[^>]*>(.*?)</a>',
    re.S)
_RE_TITLE = re.compile(r'class="v-item-title[^"]*"[^>]*>(.*?)</div>', re.S)
_RE_REMARK = re.compile(r'class="v-item-bottom"[^>]*>(.*?)</div>', re.S)
_RE_IMG = re.compile(r'data-original="([^"]+\.(?:jpg|png|webp|jpeg)[^"]*)"',
                     re.I)
_RE_DETAIL_TITLE = re.compile(
    r'class="detail-title"[^>]*>(.*?)</div>', re.S)
_RE_STRONG = re.compile(r'<strong[^>]*>(.*?)</strong>', re.S)
_RE_TITLE_TAG = re.compile(r'<title>([^<]+?)(?:-|_|高清|免费)')
_RE_INFO_ROW = re.compile(
    r'class="detail-info-row"[^>]*>.*?class="detail-info-row-side"[^>]*>'
    r'(.*?)</div>.*?class="detail-info-row-main"[^>]*>(.*?)</div>', re.S)
_RE_META_DESC = re.compile(
    r'<meta\s+name="description"\s+content="([^"]+)"', re.I)
_RE_PLAY_LINK = re.compile(r'href="(/play/%s-(\d+)-(\d+)\.html)"')
_RE_SOURCE_ITEM = re.compile(
    r'<a[^>]*class="source-item[^"]*"[^>]*>(.*?)</a>', re.S)
_RE_SRC_LABEL = re.compile(r'source-item-label[^>]*>([^<]+)<')
_RE_SRC_SUB = re.compile(r'source-item-sublabel[^>]*>([^<]+)<')
_RE_EPISODE_LIST = re.compile(
    r'<div class="episode-list"[^>]*>(.*?)</div>', re.S)
_RE_EP_A = re.compile(
    r'<a[^>]*href="(/play/\d+-\d+-\d+\.html)"[^>]*>(.*?)</a>', re.S)
_RE_SEARCH_ITEM = re.compile(
    r'<a[^>]*href="(/detail/(\d+)\.html)"[^>]*'
    r'class="search-result-item"[^>]*>(.*?)</a>', re.S)
_RE_ATTR_TITLE = re.compile(r'title="([^"]+)"')
_RE_ATTR_ALT = re.compile(r'alt="([^"]+)"')
_RE_SEARCH_TITLE = re.compile(
    r'class="[^"]*search-result-item-title[^"]*"[^>]*>(.*?)</div>', re.S)
_RE_SEARCH_FOOTER = re.compile(
    r'class="search-result-item-footer"[^>]*>(.*?)</div>', re.S)
_RE_TOKEN = re.compile(r'name="t"[^>]*value="([^"]+)"')

_RE_M3U8_PATTERNS = [
    re.compile(r'playSource\s*=\s*\{[\s\S]*?src:\s*["\']([^"\']+)["\']'),
    re.compile(r'playSource\s*\.\s*src\s*=\s*["\']([^"\']+)["\']'),
    re.compile(r'src\s*:\s*["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
               re.I),
    re.compile(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', re.I),
    re.compile(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', re.I),
]

# ===================== 文件缓存 =====================


def _cat_load():
    try:
        with _CAT_LOCK:
            if os.path.exists(_CAT_FILE):
                with open(_CAT_FILE, encoding='utf-8') as f:
                    return json.load(f)
    except Exception:
        pass
    return {}


def _cat_save(d):
    try:
        with _CAT_LOCK:
            tmp = _CAT_FILE + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False)
            os.replace(tmp, _CAT_FILE)
    except Exception:
        pass


# ===================== Spider =====================
class Spider(Spider):

    def getName(self):
        return '电影侠'

    def init(self, extend=''):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.host = (self.extend.get('site') or HOST).rstrip('/')
        self.pic_cdn = PIC_CDN
        self.ua = UA
        self.default_pic = ''
        self._token = ''
        self._token_t = 0
        self._cat_cache = _CAT_CACHE
        self.log('init: host=%s' % self.host)

    def log(self, *a, **kw):
        try:
            print('[dyx00]', *a)
        except Exception:
            pass

    # ---------- 基础工具 ----------
    def _get(self, u, timeout=6, retry=1):
        global _SESS
        h = {'User-Agent': self.ua, 'Referer': self.host + '/'}
        if _SESS is None:
            with _SESS_LOCK:
                if _SESS is None:
                    _SESS = requests.Session()
        for _ in range(retry + 1):
            try:
                r = _SESS.get(u, headers=h, timeout=timeout, verify=False)
                r.encoding = 'utf-8'
                return r.text
            except Exception:
                time.sleep(0.2)
        return ''

    def _fix_url(self, u):
        if not u:
            return ''
        u = u.strip()
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('http'):
            return u
        if u.startswith('/'):
            return self.host + u
        return urllib.parse.urljoin(self.host + '/', u)

    def _clean(self, s):
        return re.sub(
            r'\s+', ' ',
            re.sub(r'<[^>]+>', '', unicodedata.normalize('NFKC', s or ''))
        ).strip()

    def _is_wm(self, s):
        t = (s or '').lower()
        return any(w in t for w in WM)

    def _pic(self, p):
        if not p or 'logo_placeholder' in p:
            return ''
        return p if p.startswith('http') else self.pic_cdn + p

    # ---------- 列表解析 ----------
    def _extract_videos(self, html):
        out, seen = [], set()
        if not html:
            return out
        for m in _RE_ITEM.finditer(html):
            vid, inner = m.group(2), m.group(3)
            if vid in seen:
                continue
            title = remark = ''
            for t in _RE_TITLE.findall(inner):
                c = self._clean(t)
                if c and not self._is_wm(c):
                    title = c
                    break
            rb = _RE_REMARK.search(inner)
            if rb:
                remark = self._clean(rb.group(1))
            pic = ''
            for im in _RE_IMG.findall(inner):
                pic = self._pic(im)
                if pic:
                    break
            if title and pic:
                seen.add(vid)
                out.append({
                    'vod_id': vid, 'vod_name': title,
                    'vod_pic': pic, 'vod_remarks': remark,
                })
        return out

    def isVideoFormat(self, u):
        return any(x in u for x in ('.m3u8', '.mp4', '.flv'))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        global _SESS
        try:
            if _SESS is not None:
                _SESS.close()
        except Exception:
            pass
        _SESS = None

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        return {'class': CLASSES, 'filters': FILTERS, 'list': []}

    def homeVideoContent(self):
        html = self._get(self.host + '/')
        return {'list': self._extract_videos(html) if html else []}

    # ---------- 分类接口 ----------
    def _api_detail(self, vid):
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
        except Exception:
            return self._api_detail_html(vid)
        try:
            path = '/v2/vod/detail.capi'
            params = {
                'vodId': str(vid), 'os': 'android',
                'appId': 'kkdy', 'userLevel': '0',
            }
            ts = int(time.time() * 1000)
            data = '&'.join('%s=%s' % (k, params[k]) for k in sorted(params))
            ss = ('get|%s|%s|%d|appId=kkdy&deviceCreatedAt=1785930051138'
                  '&deviceId=d2c2f3345d9b2b12|') % (path, data, ts)
            sign = hmac.new(
                _VC_HASH.encode(), ss.encode(), hashlib.sha1
            ).hexdigest()
            h = {
                'User-Agent': _VC_UA, 'appId': 'kkdy', 'os': 'android',
                'appVersion': '3.5.0',
                'package': 'com.kkdyC1V260805.T180309',
                'deviceId': 'd2c2f3345d9b2b12',
                'deviceCreatedAt': '1785930051138',
                'channelId': 'c1', 'ts': str(ts), 'sign': sign,
            }
            global _SESS
            if _SESS is None:
                with _SESS_LOCK:
                    if _SESS is None:
                        _SESS = requests.Session()
            r = _SESS.get(_VC + path, params=params, headers=h,
                          timeout=8, verify=False)
            if r.headers.get('Encrypted') == '1':
                j = json.loads(
                    unpad(AES.new(_VC_KEY, AES.MODE_CBC, _VC_IV)
                          .decrypt(r.content), 16)
                )
                d = j.get('data') or {}
                ch = str(d.get('channelId') or '')
                if ch:
                    return ch
        except Exception:
            pass
        return self._api_detail_html(vid)

    def _api_detail_html(self, vid):
        html = self._get('%s/detail/%s.html' % (self.host, vid), timeout=8)
        if not html:
            return ''
        m = re.search(
            r'class="detail-info-row"[^>]*>.*?class="detail-info-row-side"[^>]*>'
            r'\s*分类\s*</div>.*?class="detail-info-row-main"[^>]*>(.*?)</div>',
            html, re.S)
        if not m:
            return ''
        c = self._clean(m.group(1))
        for key, val in (('电影', '1'), ('连续剧', '2'), ('动漫', '3'),
                         ('综艺', '4'), ('短剧', '6')):
            if key in c:
                return val
        return ''

    def _build_split(self):
        import concurrent.futures as cf
        items = {}
        pgs = list(range(1, 31))

        def gp(pg):
            h = self._get('%s/new/%d.html' % (self.host, pg), timeout=15)
            return pg, self._extract_videos(h) if h else []

        with cf.ThreadPoolExecutor(10) as ex:
            for pg, lst in ex.map(gp, pgs):
                if not lst:
                    break
                for it in lst:
                    items[it['vod_id']] = it

        buckets = {'1': [], '2': [], '3': [], '4': [], '6': []}
        ids = list(items)

        def one(v):
            return v, self._api_detail(v)

        with cf.ThreadPoolExecutor(12) as ex:
            for v, ch in ex.map(one, ids):
                if ch in buckets:
                    buckets[ch].append(items[v])
        return buckets

    def _get_split(self):
        global _SPLIT_CACHE, _SPLIT_BUILDING
        now = time.time()
        if _SPLIT_CACHE and now - _SPLIT_CACHE.get('t', 0) < 86400:
            return _SPLIT_CACHE['b']
        try:
            if os.path.exists(_SPLIT_FILE):
                with open(_SPLIT_FILE, encoding='utf-8') as f:
                    d = json.load(f)
                if d.get('t', 0) and now - d['t'] < 86400:
                    _SPLIT_CACHE = d
                    return d['b']
        except Exception:
            pass
        with _SPLIT_LOCK:
            if _SPLIT_BUILDING:
                return None
            _SPLIT_BUILDING = True

        def _bg():
            global _SPLIT_CACHE, _SPLIT_BUILDING
            try:
                b = self._build_split()
                d = {'t': time.time(), 'b': b}
                _SPLIT_CACHE = d
                try:
                    with open(_SPLIT_FILE, 'w', encoding='utf-8') as f:
                        json.dump(d, f, ensure_ascii=False)
                except Exception:
                    pass
            except Exception:
                pass
            finally:
                with _SPLIT_LOCK:
                    _SPLIT_BUILDING = False

        threading.Thread(target=_bg, daemon=True).start()
        return None

    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        pg = int(pg or 1)
        tid = str(tid)
        if tid in ('1', '2', '3', '4', '6'):
            b = self._get_split()
            if b is not None:
                lst = b.get(tid, [])
                total = len(lst)
                pagecount = max(1, (total + 23) // 24)
                if pg > pagecount:
                    return {'page': pg, 'pagecount': pagecount,
                            'limit': 24, 'total': total, 'list': []}
                return {'page': pg, 'pagecount': pagecount, 'limit': 24,
                        'total': total,
                        'list': lst[(pg - 1) * 24:pg * 24]}

        key = 'new_%d' % pg if tid == 'new' else tid
        now = time.time()
        hit = _CAT_CACHE.get(key)
        if not hit or now - hit['t'] > 300:
            fd = _cat_load()
            fh = fd.get(key) if isinstance(fd, dict) else None
            if fh and now - fh.get('t', 0) < 86400:
                hit = {'h': fh.get('h', ''), 't': fh.get('t', 0)}
            else:
                if tid == 'new':
                    html = self._get('%s/new/%d.html' % (self.host, pg),
                                     timeout=15)
                else:
                    html = self._get('%s/channel/%s.html' % (self.host, tid),
                                     timeout=15)
                hit = {'h': html, 't': now}
                if html:
                    _CAT_CACHE[key] = hit
                    fd[key] = {'h': html, 't': now}
                    _cat_save(fd)
        html = hit['h']
        items = self._extract_videos(html) if html else []

        if tid == 'new':
            pagecount = pg + 1 if items else pg
            if pg < 40 and items:
                def _pf():
                    try:
                        k2 = 'new_%d' % (pg + 1)
                        if k2 not in _CAT_CACHE:
                            h2 = self._get(
                                '%s/new/%d.html' % (self.host, pg + 1),
                                timeout=6)
                            if h2:
                                _CAT_CACHE[k2] = {'h': h2, 't': time.time()}
                                fd = _cat_load()
                                fd[k2] = {'h': h2, 't': time.time()}
                                _cat_save(fd)
                    except Exception:
                        pass

                threading.Thread(target=_pf, daemon=True).start()
            return {'page': pg, 'pagecount': pagecount, 'limit': 24,
                    'total': pagecount * 24, 'list': items}

        if pg > 1:
            return {'page': pg, 'pagecount': 1, 'limit': 0,
                    'total': len(items), 'list': []}
        return {'page': 1, 'pagecount': 1, 'limit': 48,
                'total': len(items), 'list': items}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        vid = str(ids[0])
        html = self._get('%s/detail/%s.html' % (self.host, vid))
        self.log('detail: %s HTML=%d' % (vid, len(html or '')))
        if not html:
            return {'list': []}
        vod = {'vod_id': vid}
        ts = _RE_DETAIL_TITLE.search(html)
        parts = []
        if ts:
            for s in _RE_STRONG.findall(ts.group(1)):
                c = self._clean(s)
                if c and not self._is_wm(c):
                    parts.append(c)
        vod['vod_name'] = ''.join(parts).strip()
        if not vod['vod_name']:
            m = _RE_TITLE_TAG.search(html)
            vod['vod_name'] = self._clean(m.group(1)) if m else ''
        pic = ''
        for im in _RE_IMG.findall(html):
            pic = self._pic(im)
            if pic:
                break
        vod['vod_pic'] = pic
        for k in ('vod_remarks', 'vod_year', 'vod_area', 'vod_director',
                  'vod_actor', 'vod_content'):
            vod[k] = ''
        for label, content in _RE_INFO_ROW.findall(html):
            label = self._clean(label)
            content = self._clean(content)
            if '导演' in label:
                vod['vod_director'] = content
            elif '演员' in label or '主演' in label:
                vod['vod_actor'] = content
            elif '状态' in label:
                vod['vod_remarks'] = content
            elif '地区' in label:
                vod['vod_area'] = content
            elif '年份' in label:
                vod['vod_year'] = content
        dc = _RE_META_DESC.search(html)
        _desc = self._clean(dc.group(1)) if dc else ''
        vod['vod_content'] = (INTRO_PREFIX + _desc) if _desc else ''

        # 剧集列表：按集数排序，避免 dict 去重后乱序
        raw_links = _RE_PLAY_LINK.findall(html) if False else \
            re.findall(r'href="(/play/%s-(\d+)-(\d+)\.html)"' % vid, html)
        seen, links = set(), []
        for full, sid, eid in raw_links:
            if full not in seen:
                seen.add(full)
                links.append((full, int(sid), int(eid)))
        links.sort(key=lambda x: (x[1], x[2]))
        links = [x[0] for x in links]

        pf, pu = [], []
        if links:
            ph = self._get(self.host + links[0])
            if ph:
                names = []
                for it in _RE_SOURCE_ITEM.findall(ph):
                    lb = _RE_SRC_LABEL.search(it)
                    sb = _RE_SRC_SUB.search(it)
                    lb = self._clean(lb.group(1)) if lb else ''
                    sb = self._clean(sb.group(1)) if sb else ''
                    names.append(
                        '%s(%s)' % (lb, sb) if lb and sb
                        else (lb or '线路%d' % (len(names) + 1)))
                epl = _RE_EPISODE_LIST.findall(ph)
                lines = []
                for i, el in enumerate(epl[:len(names)]):
                    nm = names[i]
                    if self._is_wm(nm) or any(
                            k in nm.lower() for k in SKIP):
                        continue
                    eps = []
                    for eu, ein in _RE_EP_A.findall(el):
                        en = self._clean(ein) or '第%d集' % (len(eps) + 1)
                        eps.append('%s$%s' % (en, eu))
                    if eps:
                        lines.append((nm, '#'.join(eps)))
                if lines:
                    lines.sort(key=lambda x: (
                        0 if ('蓝光' in x[0] and '高清' in x[0])
                        else (1 if '蓝光3' in x[0] else 2)))
                    pf = [x[0] for x in lines]
                    pu = [x[1] for x in lines]
            if not pf:
                pf.append('线路1')
                pu.append('#'.join(
                    '第%d集$%s' % (i + 1, u) for i, u in enumerate(links)))
        vod['vod_play_from'] = '$$$'.join(pf)
        vod['vod_play_url'] = '$$$'.join(pu)
        return {'list': [vod]}

    # ---------- 搜索 ----------
    def _refresh_token(self):
        h = self._get(self.host + '/')
        m = _RE_TOKEN.search(h or '')
        self._token = m.group(1) if m else ''
        self._token_t = time.time()

    def searchContent(self, key, quick, pg='1'):
        if not self._token or time.time() - self._token_t > 300:
            self._refresh_token()
        if not self._token:
            return {'list': [], 'page': 1, 'pagecount': 1,
                    'limit': 0, 'total': 0}
        url = '%s/search?k=%s&t=%s' % (
            self.host,
            urllib.parse.quote(key, safe=''),
            urllib.parse.quote(self._token, safe=''))
        if str(pg) != '1':
            url += '&page=%s' % pg
        html = self._get(url)
        videos, seen = [], set()
        if html:
            for m in _RE_SEARCH_ITEM.finditer(html):
                vid, inner = m.group(2), m.group(3)
                if vid in seen:
                    continue
                title = ''
                for pat in (_RE_ATTR_TITLE, _RE_ATTR_ALT):
                    tm = pat.search(inner)
                    if tm:
                        c = self._clean(tm.group(1))
                        if c and not self._is_wm(c):
                            title = c
                            break
                if not title:
                    for t in _RE_SEARCH_TITLE.findall(inner):
                        c = self._clean(t)
                        if c and not self._is_wm(c):
                            title = c
                            break
                fb = _RE_SEARCH_FOOTER.search(inner)
                pic = ''
                for im in _RE_IMG.findall(inner):
                    pic = self._pic(im)
                    if pic:
                        break
                if title and pic:
                    seen.add(vid)
                    videos.append({
                        'vod_id': vid, 'vod_name': title,
                        'vod_pic': pic,
                        'vod_remarks': self._clean(fb.group(1)) if fb else '',
                    })
        page = int(pg or 1)
        return {
            'list': videos, 'page': page,
            'pagecount': page + 1 if videos else page,
            'limit': len(videos), 'total': len(videos),
        }

    # ---------- 播放 ----------
    def _extract_m3u8(self, html):
        if not html:
            return ''
        for pat in _RE_M3U8_PATTERNS:
            m = pat.search(html)
            if m:
                return m.group(1).replace('\\/', '/')
        return ''

    def playerContent(self, flag, id, vipFlags=None):
        u = str(id)
        if not u.startswith('http'):
            u = self.host + u
        html = self._get(u)
        url = self._extract_m3u8(html)

        if not url:
            vm = re.search(r'/play/(\d+)-', u)
            if vm:
                vid = vm.group(1)
                dh = self._get('%s/detail/%s.html' % (self.host, vid))
                for lu in re.findall(
                        r'href="(/play/%s-\d+-\d+\.html)"' % vid, dh or ''):
                    if lu in u:
                        continue
                    ph2 = self._get(self.host + lu)
                    url = self._extract_m3u8(ph2)
                    if url:
                        break

        header = {'User-Agent': self.ua, 'Referer': self.host + '/'}
        if url and self.isVideoFormat(url):
            return {'parse': 0, 'url': url, 'header': header}
        if url:
            return {'parse': 1, 'url': url, 'header': header}
        return {'parse': 0, 'url': '', 'header': header}
