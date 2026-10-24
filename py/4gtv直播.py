# coding=utf-8
"""
4GTV 双代理直播源 | TVBox Python 爬虫 
关键:
  - 静态频道表 CHANNELS，按内容类型分 10 类：
    新聞財經 / 綜合娛樂 / 影視戲劇 / 兒童卡通 / 體育電競 /
    音樂頻道 / 生活旅遊 / 紀實知識 / 宗教國會 / 購物其他
  - 双代理：4GTV 组经 caonizuzong.cc.cd；歐菲组经 live.yiwo.uk:50002
  - 每个频道标注来源 (4GTV / 歐菲)，vod_remarks 与播放线路名均显示来源
  - 同一频道多源并存时，各自成条目，方便源挂了切换
  - 直接返回代理网址 (parse=0)，无需嗅探；播放结果做 10 分钟内存缓存
"""
import sys
import json
import time

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
                print("[4gtv2]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


# ===================== 常量 =====================
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

CATEGORY_ORDER = [
    "新聞財經", "綜合娛樂", "影視戲劇", "兒童卡通", "體育電競",
    "音樂頻道", "生活旅遊", "紀實知識", "宗教國會", "購物其他",
]

# 每条频道：[名称, 播放地址, Logo, 来源]
# 来源：'4GTV' 或 '歐菲'
# 注意：Bloomberg TV 与 东森购物四 原始 URL 均为 4gtv-live049，疑似原数据重复，保留待核
CHANNELS = {
    '新聞財經': [
        # ---- 4GTV 源 ----
        ['东森新闻', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv152', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv14_mobile.png', '4GTV'],
        ['台视新闻', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv051', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv051_mobile.png', '4GTV'],
        ['华视新闻', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv052', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv052_mobile.png', '4GTV'],
        ['民视新闻', 'https://www.caonizuzong.cc.cd/4gtv?id=live-ftv13', '', '4GTV'],
        ['三立新闻iNEWS', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live089', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live089_mobile.png', '4GTV'],
        ['TVBS新闻', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv072', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv072_mobile.png', '4GTV'],
        ['东森财经新闻', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv153', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv019_mobile.png', '4GTV'],
        ['中视新闻', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv074', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv074_mobile.png', '4GTV'],
        ['中天新闻', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv009', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv009_mobile.png', '4GTV'],
        ['寰宇新闻', 'https://www.caonizuzong.cc.cd/4gtv?id=litv-longturn14', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-longturn14.png', '4GTV'],
        ['寰宇新闻台湾', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv156', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv156.png', '4GTV'],
        ['新唐人亚太', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live050', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live050_mobile.png', '4GTV'],
        ['Bloomberg TV', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live049', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live047_mobile.webp', '4GTV'],
        ['SBN全球财经', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live060', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live060_mobile.png', '4GTV'],
        ['寰宇财经', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv158', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv158.png', '4GTV'],
        ['VOA美国之音', 'https://www.caonizuzong.cc.cd/4gtv?id=litv-ftv03', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv03_mobile.png', '4GTV'],
        ['CNBCAsia财经', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live130', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv130_mobile.png', '4GTV'],
        ['DW德国之声', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live071', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live071_mobile.png', '4GTV'],
        ['镜电视新闻', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv075', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv075_mobile.png', '4GTV'],
        # ---- 歐菲 源 ----
        ['中天新聞台', 'http://live.yiwo.uk:50002/index.m3u8?pid=4gtv-4gtv009&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv009_mobile.png', '歐菲'],
        ['華視新聞', 'http://live.yiwo.uk:50002/index.m3u8?pid=4gtv-4gtv052&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv052_mobile.png', '歐菲'],
        ['中視新聞', 'http://live.yiwo.uk:50002/index.m3u8?pid=4gtv-4gtv074&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv074_mobile.png', '歐菲'],
        ['第1商業台', 'http://live.yiwo.uk:50002/index.m3u8?pid=4gtv-4gtv104&sd=1080&proxy=false&token=yiwo', '', '歐菲'],
        ['寰宇新聞台灣台', 'http://live.yiwo.uk:50002/index.m3u8?pid=4gtv-4gtv156&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv156.png', '歐菲'],
        ['寰宇財經台', 'http://live.yiwo.uk:50002/index.m3u8?pid=4gtv-4gtv158&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv158.png', '歐菲'],
        ['三立新聞iNEWS', 'http://live.yiwo.uk:50002/index.m3u8?pid=iNEWS&sd=1080&proxy=false&token=yiwo', '', '歐菲'],
        ['寰宇新聞台', 'http://live.yiwo.uk:50002/index.m3u8?pid=litv-longturn14&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-longturn14.png', '歐菲'],
        ['倪珍播新聞', 'http://live.yiwo.uk:50002/index.m3u8?pid=nnews-zh&sd=1080&proxy=false&token=yiwo', '', '歐菲'],
    ],
    '綜合娛樂': [
        # ---- 4GTV 源 ----
        ['民视', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv002', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv002_mobile.png', '4GTV'],
        ['中视', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv040', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv040_mobile.png', '4GTV'],
        ['华视', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv041', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv041_mobile.png', '4GTV'],
        ['三立综合', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live207', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live207_mobile.png', '4GTV'],
        ['TVBS', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv073', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv073_mobile.png', '4GTV'],
        ['民视第一', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv003', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv003_mobile.png', '4GTV'],
        ['民视台湾', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv001', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv001_mobile.png', '4GTV'],
        ['TVBS精采', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv067', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live086_mobile.png', '4GTV'],
        ['客家电视', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv043', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv043_mobile.png', '4GTV'],
        ['八大综综艺', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv039', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv039_mobile.png', '4GTV'],
        ['中视菁采', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv064', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live206_mobile.webp', '4GTV'],
        ['爱尔达娱乐', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv070', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_INULTRA_mobile.webp', '4GTV'],
        ['靖天综合', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv046', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv046_mobile.png', '4GTV'],
        ['靖天日本', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv047', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv047_mobile.png', '4GTV'],
        ['ARIRANG阿里郎频道', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv079', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv079_1_mobile.png', '4GTV'],
        ['原住民族电视', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live014', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live014_mobile.png', '4GTV'],
        ['民视综艺', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv004', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv004_mobile.png', '4GTV'],
        ['猪哥亮歌厅秀', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv006', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv006_mobile.png', '4GTV'],
        ['靖天育乐', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv062', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv062_mobile.png', '4GTV'],
        ['靖天国际', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv063', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv063_mobile.png', '4GTV'],
        ['靖天欢乐', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv054', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv054_mobile.png', '4GTV'],
        ['靖天资讯', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv065', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv065_mobile.png', '4GTV'],
        ['TVBS欢乐', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv068', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv068_mobile.png', '4GTV'],
        ['TVBS综艺', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live087', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live087_mobile.png', '4GTV'],
        ['韩国娱乐', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv016', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv016_mobile.png', '4GTV'],
        ['ROCK Entertainment', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live080', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live080_mobile.png', '4GTV'],
        ['Lifetime 娱乐频道', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live029', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live029_mobile.png', '4GTV'],
        ['八大精彩', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv034', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv034_mobile_0211.png', '4GTV'],
        # ---- 歐菲 源 ----
        ['中視', 'http://live.yiwo.uk:50002/index.m3u8?pid=4gtv-4gtv040&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv040_mobile.png', '歐菲'],
        ['華視', 'http://live.yiwo.uk:50002/index.m3u8?pid=4gtv-4gtv041&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv041_mobile.png', '歐菲'],
    ],
    '影視戲劇': [
        # ---- 4GTV 源 ----
        ['中视经典', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv080', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live014_mobile.webp', '4GTV'],
        ['TVBS台剧', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live088', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/4gtv-live088.png', '4GTV'],
        ['公视戏剧', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv042', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv042_mobile.png', '4GTV'],
        ['民视影剧', 'https://www.caonizuzong.cc.cd/4gtv?id=litv-ftv09', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv09_mobile.png', '4GTV'],
        ['HITS频道', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live620', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live620_mobile.png', '4GTV'],
        ['霹雳布袋戏', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live145', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live145_mobile.png', '4GTV'],
        ['靖天戏剧', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv058', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv058_mobile.png', '4GTV'],
        ['靖洋戏剧', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv045', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv045_mobile.png', '4GTV'],
        ['金光布袋戏', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live144', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live144_mobile.png', '4GTV'],
        ['ROCKAction', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live138', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/live138_mobile.png', '4GTV'],
        ['采昌影剧', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv049', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv049_mobile.png', '4GTV'],
        ['靖天映画', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv055', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv055_mobile.png', '4GTV'],
        ['靖天电影', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv061', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv061_mobile.png', '4GTV'],
        ['影迷数位电影', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv011', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv011_mobile-1.png', '4GTV'],
        ['amc电影', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv017', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv017new_mobile.png', '4GTV'],
        ['CinemaWorld', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live069', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live069_mobile.png', '4GTV'],
        ['我的欧洲电影', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live157', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv10_mobile.png', '4GTV'],
        ['经典电影', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live021', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live021_mobile.png', '4GTV'],
        ['戏剧免费看1', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live010', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live010_mobile.png', '4GTV'],
        # ---- 歐菲 源 ----
        ['龍華洋片台', 'http://live.yiwo.uk:50002/index.m3u8?pid=litv-xinchuang02&sd=1080&proxy=false&token=yiwo', '', '歐菲'],
        ['龍華電影台', 'http://live.yiwo.uk:50002/index.m3u8?pid=litv-xinchuang03&sd=1080&proxy=false&token=yiwo', '', '歐菲'],
        ['龍華日韓台', 'http://live.yiwo.uk:50002/index.m3u8?pid=litv-xinchuang11&sd=1080&proxy=false&token=yiwo', '', '歐菲'],
        ['龍華偶像台', 'http://live.yiwo.uk:50002/index.m3u8?pid=litv-xinchuang12&sd=1080&proxy=false&token=yiwo', '', '歐菲'],
        ['龍華戲劇台', 'http://live.yiwo.uk:50002/index.m3u8?pid=litv-xinchuang18&sd=1080&proxy=false&token=yiwo', '', '歐菲'],
        ['龍華經典台', 'http://live.yiwo.uk:50002/index.m3u8?pid=litv-xinchuang21&sd=1080&proxy=false&token=yiwo', '', '歐菲'],
        ['台灣戲劇台', 'http://live.yiwo.uk:50002/index.m3u8?pid=litv-xinchuang22&sd=1080&proxy=false&token=yiwo', '', '歐菲'],
    ],
    '兒童卡通': [
        # ---- 4GTV 源 ----
        ['Nick Jr. 儿童频道', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live032', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live032.png', '4GTV'],
        ['尼克儿童频道', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live105', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live105.png', '4GTV'],
        ['DreamWorks 梦工厂动画', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live017', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live017_mobile.png', '4GTV'],
        ['靖天卡通', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv044', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv044_mobile.png', '4GTV'],
        ['靖洋卡通Nice Bingo', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv057', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv057_mobile.png', '4GTV'],
        ['MOMO亲子', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live107', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/4gtv-live107.png', '4GTV'],
        ['经典卡通', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live022', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live022_mobile.png', '4GTV'],
        ['精选动漫', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live024', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live024_mobile.png', '4GTV'],
        # ---- 歐菲 源 ----
        ['龍華卡通台', 'http://live.yiwo.uk:50002/index.m3u8?pid=litv-xinchuang01&sd=1080&proxy=false&token=yiwo', '', '歐菲'],
    ],
    '體育電競': [
        # ---- 4GTV 源 ----
        ['TRACESportStars', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv077', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv077_mobile.png', '4GTV'],
        ['智林体育', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv101', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv101_mobile.png', '4GTV'],
        ['时尚运动X', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv014', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv014_mobile.png', '4GTV'],
        ['车迷TV', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live201', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live201_mobile.png', '4GTV'],
        ['GINXEsportsTV', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv053', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv053_mobile.png', '4GTV'],
    ],
    '音樂頻道': [
        # ---- 4GTV 源 ----
        ['电影原声', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live031', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live031_mobile.png', '4GTV'],
        ['TRACEUrban', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv082', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv082_mobile.png', '4GTV'],
        ['MTVLiveHD音乐频道', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live025', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live025_mobile.png', '4GTV'],
        ['MezzoLiveHD', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv083', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv083_mobile.png', '4GTV'],
        ['CLASSICA古典乐', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv059', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv059_mobile.png', '4GTV'],
    ],
    '生活旅遊': [
        # ---- 4GTV 源 ----
        ['PetClubTV', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live110', '', '4GTV'],
        ['民视旅游Fre', 'https://www.caonizuzong.cc.cd/4gtv?id=litv-ftv07', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv07_mobile.png', '4GTV'],
        ['滚动力rollor', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live012', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live012_mobile.png', '4GTV'],
        ['亚洲旅游', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv076', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-longturn17_mobile.png', '4GTV'],
        ['fun探索娱乐', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live011', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live011_mobile.png', '4GTV'],
        ['幸福空间居家', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live206', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live206_mobile.png', '4GTV'],
        ['爱尔达生活旅游', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live120', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live120_mobile.png', '4GTV'],
        ['LUXETVChannel', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live121', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live121_mobile.png', '4GTV'],
        ['TV5MONDESTYLEHD生活时尚', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live122', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live122_mobile.png', '4GTV'],
        ['LiveABC互动英语频道', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live030', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live030_mobile.png', '4GTV'],
        ['ELTV生活英语', 'https://www.caonizuzong.cc.cd/4gtv?id=litv-longturn20', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-longturn20_mobile.png', '4GTV'],
        # ---- 歐菲 源 ----
        ['亞洲旅遊台', 'http://live.yiwo.uk:50002/index.m3u8?pid=4gtv-4gtv076&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-longturn17_mobile.png', '歐菲'],
        ['ELTV生活英語台', 'http://live.yiwo.uk:50002/index.m3u8?pid=litv-xinchuang20&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-longturn20_mobile.webp', '歐菲'],
    ],
    '紀實知識': [
        # ---- 4GTV 源 ----
        ['Global Trekker', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live112', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live112_mobile.png', '4GTV'],
        ['达文西频道', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv018', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv018_mobile.png', '4GTV'],
        ['LoveNature', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live208', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/ogo_4gtv_4gtv-live208_mobile.png', '4GTV'],
        ['History历史频道', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live026', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live026_mobile.png', '4GTV'],
        ['CI罪案侦查频道', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live027', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live027_mobile.png', '4GTV'],
        ['视纳华仁纪实频道', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv013', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv013_mobile.png', '4GTV'],
        ['影迷数位纪实', 'https://www.caonizuzong.cc.cd/4gtv?id=litv-ftv15', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live023_mobile.png', '4GTV'],
        # ---- 歐菲 源 ----
        ['Smart知識台', 'http://live.yiwo.uk:50002/index.m3u8?pid=litv-xinchuang19&sd=1080&proxy=false&token=yiwo', '', '歐菲'],
    ],
    '宗教國會': [
        # ---- 4GTV 源 ----
        ['大爱电视', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv007', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv007_mobile.png', '4GTV'],
        ['好消息', 'https://www.caonizuzong.cc.cd/4gtv?id=litv-ftv16', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv16_mobile.png', '4GTV'],
        ['好消息2', 'https://www.caonizuzong.cc.cd/4gtv?id=litv-ftv17', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv17_mobile.png', '4GTV'],
        ['大爱二', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live106', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live106_mobile.png', '4GTV'],
        ['人间卫视', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live008', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live008_mobile.png', '4GTV'],
        ['国会频道1', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv084', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv084_mobile_0204.png', '4GTV'],
        ['国会频道2', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-4gtv085', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv085_mobile_0204.png', '4GTV'],
        # ---- 歐菲 源 ----
        ['國會頻道1台', 'http://live.yiwo.uk:50002/index.m3u8?pid=4gtv-4gtv084&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv084_mobile_0204.png', '歐菲'],
        ['國會頻道2台', 'http://live.yiwo.uk:50002/index.m3u8?pid=4gtv-4gtv085&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv085_mobile_0204.png', '歐菲'],
        ['DayStar', 'http://live.yiwo.uk:50002/index.m3u8?pid=daystar&sd=1080&proxy=false&token=yiwo', '', '歐菲'],
        ['好消息', 'http://live.yiwo.uk:50002/index.m3u8?pid=litv-ftv16&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv16_mobile.png', '歐菲'],
        ['好消息2台', 'http://live.yiwo.uk:50002/index.m3u8?pid=litv-ftv17&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv17_mobile.png', '歐菲'],
    ],
    '購物其他': [
        # ---- 4GTV 源 ----
        ['东森购物四', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live049', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live047_mobile.webp', '4GTV'],
        ['东森购物一', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live047', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live047_mobile.png', '4GTV'],
        ['东森购物二', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live046', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live047_mobile.webp', '4GTV'],
        ['东森购物三', 'https://www.caonizuzong.cc.cd/4gtv?id=4gtv-live048', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live047_mobile.png', '4GTV'],
        # ---- 歐菲 源 ----
        ['東森購物1台', 'http://live.yiwo.uk:50002/index.m3u8?pid=4gtv-4gtv102&sd=1080&proxy=false&token=yiwo', '', '歐菲'],
        ['東森購物2台', 'http://live.yiwo.uk:50002/index.m3u8?pid=4gtv-4gtv103&sd=1080&proxy=false&token=yiwo', 'https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv103_mobile.png', '歐菲'],
    ],
}


# ===================== 爬虫主体 =====================
class Spider(Spider):

    def getName(self):
        return "4GTV双代理"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.4gtv.tv/",
        }
        self._play_cache = {}
        self.log("init: 共 %d 个分类, %d 个频道条目" % (
            len(CATEGORY_ORDER),
            sum(len(v) for v in CHANNELS.values())))

    # ---------- 工具 ----------
    def _fetch(self, url, timeout=15, headers=None):
        """预留：频道表为静态数据，当前无需网络请求，保留以统一风格。"""
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            return getattr(rsp, "text", "") or ""
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _vod(self, tid, i, item):
        name, url, logo, source = item
        return {
            "vod_id":      "%s|%d" % (tid, i),
            "vod_name":    name,
            "vod_pic":     logo,
            "vod_remarks": source,
        }

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        classes = [{"type_name": c, "type_id": c} for c in CATEGORY_ORDER]
        return {"class": classes}

    def homeVideoContent(self):
        # 每类取前 3 个做首页推荐
        vods = []
        for tid in CATEGORY_ORDER:
            for i, item in enumerate(CHANNELS.get(tid, [])[:3]):
                vods.append(self._vod(tid, i, item))
        self.log("homeVideoContent: %d 条" % len(vods))
        return {"list": vods}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        items = CHANNELS.get(tid, [])
        vods = [self._vod(tid, i, item) for i, item in enumerate(items)]
        self.log("categoryContent: %s -> %d 条" % (tid, len(vods)))
        return {
            "page": 1,
            "pagecount": 1,
            "limit": len(vods),
            "total": len(vods),
            "list": vods,
        }

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        try:
            tid, idx = vid.rsplit("|", 1)
            name, url, logo, source = CHANNELS[tid][int(idx)]
        except Exception as e:
            self.log("detail 解析失败: %s" % e)
            return {"list": []}

        vod = {
            "vod_id":        vid,
            "vod_name":      name,
            "vod_pic":       logo,
            "vod_remarks":   source,
            "vod_play_from": source,
            "vod_play_url":  "直播$" + vid,
        }
        self.log("detail: %s (%s)" % (name, source))
        return {"list": [vod]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        now = int(time.time())
        if id in self._play_cache:
            ts, res = self._play_cache[id]
            if now - ts < 600:
                return res

        try:
            tid, idx = id.rsplit("|", 1)
            name, url, logo, source = CHANNELS[tid][int(idx)]
        except Exception as e:
            self.log("player 解析失败: %s" % e)
            return {"parse": 1, "playUrl": "", "url": "", "header": {}}

        res = {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": {"User-Agent": UA},
        }
        self._play_cache[id] = (now, res)
        self.log("player: %s (%s)" % (name, source))
        return res

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        vods = []
        for tid in CATEGORY_ORDER:
            for i, item in enumerate(CHANNELS.get(tid, [])):
                if key in item[0]:
                    vods.append(self._vod(tid, i, item))
        self.log("search '%s' -> %d 条" % (key, len(vods)))
        return {"list": vods}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 其他 ----------
    def localProxy(self, param):
        # 4GTV 频道 Logo 来自官方图床，暂不需要本地代理
        return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        self._play_cache = {}

    def close(self):
        self.destroy()
