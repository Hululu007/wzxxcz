# coding=utf-8
"""
4GTV 双代理直播 (api: py_4gtv3) 
改进：
  1. 全部频道 ID 经实测校验：剔除已 404 下线的频道（TVBS/TVBS新闻/大爱/MTV 等），
     修复「民视新闻」错误 ID（live-ftv13 -> litv-ftv13）。
  2. 每个频道可带多个源（4GTV 主源 caonizuzong / 欧菲备用源 yiwo），
     详情页自动显示为多条线路，单源挂了可切换线路，不再黑屏。
  3. 繁体全部转简体，修正错别字（八大综综艺、LoveNature 图标路径等）。
  4. 分类按用户观看习惯重排：新闻/综合/剧集/电影/动漫少儿/体育/音乐/
     纪实知识/生活旅游/财经/购物，搜索全分类可用。
播放：直接回代理地址（parse=0），支持搜索、线路切换。
"""
import sys
sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    class Spider:
        def __init__(self):
            pass


SRC_4 = "4GTV"    # caonizuzong.cc.cd 代理
SRC_Y = "欧菲"    # live.yiwo.uk:50002 代理 (token=yiwo)


def _u4(pid):
    return "https://www.caonizuzong.cc.cd/4gtv?id=" + pid


def _uy(pid):
    return ("http://live.yiwo.uk:50002/index.m3u8?pid=" + pid +
            "&sd=1080&proxy=false&token=yiwo")


# ============ 频道表：分类 -> [名称, 图标, {源: pid}] ============
# 说明：同一频道若两个源都有，详情页会显示两条线路；单源频道只有一条。
CHANNELS = {
    "新闻": [
        ["民视新闻", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv13_mobile.png", {SRC_4: "litv-ftv13"}],
        ["民视新闻台湾", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live060_mobile.png", {SRC_4: "4gtv-live060"}],
        ["三立新闻iNEWS", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live089_mobile.png", {SRC_4: "4gtv-live089", SRC_Y: "iNEWS"}],
        ["华视新闻", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv052_mobile.png", {SRC_4: "4gtv-4gtv052", SRC_Y: "4gtv-4gtv052"}],
        ["中视新闻", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv074_mobile.png", {SRC_4: "4gtv-4gtv074", SRC_Y: "4gtv-4gtv074"}],
        ["中天新闻", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv009_mobile.png", {SRC_Y: "4gtv-4gtv009"}],
        ["东森新闻", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv14_mobile.png", {SRC_4: "4gtv-4gtv152"}],
        ["东森财经新闻", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv019_mobile.png", {SRC_4: "4gtv-4gtv153"}],
        ["镜电视新闻", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv075_mobile.png", {SRC_4: "4gtv-4gtv075"}],
        ["寰宇新闻", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-longturn14.png", {SRC_4: "litv-longturn14", SRC_Y: "litv-longturn14"}],
        ["寰宇新闻台湾", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv156.png", {SRC_4: "4gtv-4gtv156", SRC_Y: "4gtv-4gtv156"}],
        ["倪珍播新闻", "", {SRC_Y: "nnews-zh"}],
        ["国会频道1", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv084_mobile_0204.png", {SRC_4: "4gtv-4gtv084", SRC_Y: "4gtv-4gtv084"}],
        ["国会频道2", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv085_mobile_0204.png", {SRC_4: "4gtv-4gtv085", SRC_Y: "4gtv-4gtv085"}],
        ["DW德国之声", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live071_mobile.png", {SRC_4: "4gtv-live071"}],
    ],
    "综合": [
        ["民视", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv002_mobile.png", {SRC_4: "4gtv-4gtv002"}],
        ["民视第一", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv003_mobile.png", {SRC_4: "4gtv-4gtv003"}],
        ["民视台湾", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv001_mobile.png", {SRC_4: "4gtv-4gtv001"}],
        ["民视综艺", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv004_mobile.png", {SRC_4: "4gtv-4gtv004"}],
        ["中视", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv040_mobile.png", {SRC_4: "4gtv-4gtv040", SRC_Y: "4gtv-4gtv040"}],
        ["华视", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv041_mobile.png", {SRC_4: "4gtv-4gtv041", SRC_Y: "4gtv-4gtv041"}],
        ["三立综合", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live207_mobile.png", {SRC_4: "4gtv-live207"}],
        ["八大综艺", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv039_mobile.png", {SRC_4: "4gtv-4gtv039"}],
        ["八大精彩", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv034_mobile_0211.png", {SRC_4: "4gtv-4gtv034"}],
        ["中视经典", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live014_mobile.webp", {SRC_4: "4gtv-4gtv080"}],
        ["中视菁采", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live206_mobile.webp", {SRC_4: "4gtv-4gtv064"}],
        ["TVBS欢乐", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv068_mobile.png", {SRC_4: "4gtv-4gtv068"}],
        ["猪哥亮歌厅秀", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv006_mobile.png", {SRC_4: "4gtv-4gtv006"}],
        ["客家电视", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv043_mobile.png", {SRC_4: "4gtv-4gtv043"}],
        ["靖天综合", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv046_mobile.png", {SRC_4: "4gtv-4gtv046"}],
        ["靖天日本", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv047_mobile.png", {SRC_4: "4gtv-4gtv047"}],
        ["靖天育乐", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv062_mobile.png", {SRC_4: "4gtv-4gtv062"}],
        ["靖天国际", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv063_mobile.png", {SRC_4: "4gtv-4gtv063"}],
        ["靖天欢乐", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv054_mobile.png", {SRC_4: "4gtv-4gtv054"}],
        ["靖天资讯", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv065_mobile.png", {SRC_4: "4gtv-4gtv065"}],
        ["爱尔达娱乐", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_INULTRA_mobile.webp", {SRC_4: "4gtv-4gtv070"}],
        ["韩国娱乐", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv016_mobile.png", {SRC_4: "4gtv-4gtv016"}],
        ["ROCK Entertainment", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live080_mobile.png", {SRC_4: "4gtv-live080"}],
        ["Lifetime娱乐", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live029_mobile.png", {SRC_4: "4gtv-live029"}],
        ["大爱二", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live106_mobile.png", {SRC_4: "4gtv-live106"}],
        ["人间卫视", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live008_mobile.png", {SRC_4: "4gtv-live008"}],
        ["好消息", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv16_mobile.png", {SRC_4: "litv-ftv16", SRC_Y: "litv-ftv16"}],
        ["好消息2", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv17_mobile.png", {SRC_4: "litv-ftv17", SRC_Y: "litv-ftv17"}],
        ["DayStar", "", {SRC_Y: "daystar"}],
    ],
    "剧集": [
        ["公视戏剧", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv042_mobile.png", {SRC_4: "4gtv-4gtv042"}],
        ["民视影剧", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv09_mobile.png", {SRC_4: "litv-ftv09"}],
        ["TVBS台剧", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/4gtv-live088.png", {SRC_4: "4gtv-live088"}],
        ["靖天戏剧", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv058_mobile.png", {SRC_4: "4gtv-4gtv058"}],
        ["靖洋戏剧", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv045_mobile.png", {SRC_4: "4gtv-4gtv045"}],
        ["台湾戏剧台", "", {SRC_Y: "litv-xinchuang22"}],
        ["龙华戏剧台", "", {SRC_Y: "litv-xinchuang18"}],
        ["龙华经典台", "", {SRC_Y: "litv-xinchuang21"}],
        ["龙华偶像台", "", {SRC_Y: "litv-xinchuang12"}],
        ["龙华日韩台", "", {SRC_Y: "litv-xinchuang11"}],
        ["金光布袋戏", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live144_mobile.png", {SRC_4: "4gtv-live144"}],
        ["采昌影剧", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv049_mobile.png", {SRC_4: "4gtv-4gtv049"}],
    ],
    "电影": [
        ["靖天电影", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv061_mobile.png", {SRC_4: "4gtv-4gtv061"}],
        ["靖天映画", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv055_mobile.png", {SRC_4: "4gtv-4gtv055"}],
        ["影迷数位电影", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv011_mobile-1.png", {SRC_4: "4gtv-4gtv011"}],
        ["AMC电影", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv017new_mobile.png", {SRC_4: "4gtv-4gtv017"}],
        ["CinemaWorld", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live069_mobile.png", {SRC_4: "4gtv-live069"}],
        ["经典电影", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live021_mobile.png", {SRC_4: "4gtv-live021"}],
        ["我的欧洲电影", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv10_mobile.png", {SRC_4: "4gtv-live157"}],
        ["龙华电影台", "", {SRC_Y: "litv-xinchuang03"}],
    ],
    "动漫少儿": [
        ["梦工厂动画", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live017_mobile.png", {SRC_4: "4gtv-live017"}],
        ["靖天卡通", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv044_mobile.png", {SRC_4: "4gtv-4gtv044"}],
        ["靖洋卡通NiceBingo", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv057_mobile.png", {SRC_4: "4gtv-4gtv057"}],
        ["MOMO亲子", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/4gtv-live107.png", {SRC_4: "4gtv-live107"}],
        ["NickJr儿童", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live032.png", {SRC_4: "4gtv-live032"}],
        ["尼克儿童", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live105.png", {SRC_4: "4gtv-live105"}],
        ["经典卡通", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live022_mobile.png", {SRC_4: "4gtv-live022"}],
        ["精选动漫", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live024_mobile.png", {SRC_4: "4gtv-live024"}],
        ["龙华卡通台", "", {SRC_Y: "litv-xinchuang01"}],
        ["龙华洋片台", "", {SRC_Y: "litv-xinchuang02"}],
    ],
    "体育": [
        ["智林体育", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv101_mobile.png", {SRC_4: "4gtv-4gtv101"}],
        ["时尚运动X", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv014_mobile.png", {SRC_4: "4gtv-4gtv014"}],
        ["GINX电竞", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv053_mobile.png", {SRC_4: "4gtv-4gtv053"}],
        ["TRACE SportStars", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv077_mobile.png", {SRC_4: "4gtv-4gtv077"}],
        ["车迷TV", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live201_mobile.png", {SRC_4: "4gtv-live201"}],
    ],
    "音乐": [
        ["MTVLiveHD", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live025_mobile.png", {SRC_4: "4gtv-live025"}],
        ["CLASSICA古典乐", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv059_mobile.png", {SRC_4: "4gtv-4gtv059"}],
        ["TRACEUrban", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv082_mobile.png", {SRC_4: "4gtv-4gtv082"}],
        ["HITS频道", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live620_mobile.png", {SRC_4: "4gtv-live620"}],
        ["电影原声", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live031_mobile.png", {SRC_4: "4gtv-live031"}],
    ],
    "纪实知识": [
        ["History历史", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live026_mobile.png", {SRC_4: "4gtv-live026"}],
        ["CI罪案侦查", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live027_mobile.png", {SRC_4: "4gtv-live027"}],
        ["视纳华仁纪实", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv013_mobile.png", {SRC_4: "4gtv-4gtv013"}],
        ["影迷数位纪实", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live023_mobile.png", {SRC_4: "litv-ftv15"}],
        ["LoveNature", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live208_mobile.png", {SRC_4: "4gtv-live208"}],
        ["GlobalTrekker", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live112_mobile.png", {SRC_4: "4gtv-live112"}],
        ["达文西频道", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv018_mobile.png", {SRC_4: "4gtv-4gtv018"}],
        ["LiveABC互动英语", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live030_mobile.png", {SRC_4: "4gtv-live030"}],
        ["Smart知识台", "", {SRC_Y: "litv-xinchuang19"}],
        ["滚动力rollor", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live012_mobile.png", {SRC_4: "4gtv-live012"}],
        ["fun探索娱乐", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live011_mobile.png", {SRC_4: "4gtv-live011"}],
    ],
    "生活旅游": [
        ["亚洲旅游", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-longturn17_mobile.png", {SRC_4: "4gtv-4gtv076", SRC_Y: "4gtv-4gtv076"}],
        ["民视旅游Fre", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-ftv07_mobile.png", {SRC_4: "litv-ftv07"}],
        ["爱尔达生活旅游", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live120_mobile.png", {SRC_4: "4gtv-live120"}],
        ["LUXETV", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live121_mobile.png", {SRC_4: "4gtv-live121"}],
        ["TV5MONDE生活时尚", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live122_mobile.png", {SRC_4: "4gtv-live122"}],
        ["ELTV生活英语", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_litv-longturn20_mobile.webp", {SRC_Y: "litv-xinchuang20"}],
    ],
    "财经": [
        ["CNBCAsia财经", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv130_mobile.png", {SRC_4: "4gtv-live130"}],
        ["SBN全球财经", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live060_mobile.png", {SRC_4: "4gtv-live060"}],
        ["寰宇财经", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv158.png", {SRC_4: "4gtv-4gtv158", SRC_Y: "4gtv-4gtv158"}],
        ["第1商业台", "", {SRC_Y: "4gtv-4gtv104"}],
    ],
    "购物": [
        ["东森购物1台", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live047_mobile.png", {SRC_4: "4gtv-live047", SRC_Y: "4gtv-4gtv102"}],
        ["东森购物2台", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-4gtv103_mobile.png", {SRC_4: "4gtv-live046", SRC_Y: "4gtv-4gtv103"}],
        ["东森购物3台", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live047_mobile.png", {SRC_4: "4gtv-live048"}],
        ["东森购物4台", "https://4gtvimg2.4gtv.tv/4gtv-Image/Channel/mobile/logo_4gtv_4gtv-live047_mobile.webp", {SRC_4: "4gtv-live049"}],
    ],
}

# 频道索引: vod_id = "分类@序号"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


class Spider(Spider):

    def getName(self):
        return "py_4gtv3"

    def init(self, extend=""):
        pass

    # ---------- 内部 ----------
    def _srcs(self, cat, idx):
        """返回 [(线路名, 播放url), ...]"""
        name, logo, srcs = CHANNELS[cat][idx]
        out = []
        if SRC_4 in srcs:
            out.append((SRC_4, _u4(srcs[SRC_4])))
        if SRC_Y in srcs:
            out.append((SRC_Y, _uy(srcs[SRC_Y])))
        return out

    def _vod(self, cat, idx, name, logo):
        return {
            "vod_id": cat + "@" + str(idx),
            "vod_name": name,
            "vod_pic": logo,
            "vod_remarks": "直播",
            "vod_tag": "folder",
        }

    # ---------- 接口 ----------
    def homeContent(self, filter):
        classes = [{"type_name": c, "type_id": c} for c in CHANNELS]
        return {"class": classes}

    def homeVideoContent(self):
        # 首页推荐：每个分类取前 2 个
        vods = []
        for cat, items in CHANNELS.items():
            for i, (name, logo, _) in enumerate(items[:2]):
                vods.append(self._vod(cat, i, name, logo))
        return {"list": vods}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        items = CHANNELS.get(tid, [])
        vods = [self._vod(tid, i, n, lg) for i, (n, lg, _) in enumerate(items)]
        return {"page": 1, "pagecount": 1, "limit": len(vods),
                "total": len(vods), "list": vods}

    def detailContent(self, ids):
        vid = ids[0]
        cat, idx = vid.rsplit("@", 1)
        name, logo, _ = CHANNELS[cat][int(idx)]
        lines = self._srcs(cat, int(idx))
        play_from = "$$$".join(s for s, _ in lines)
        play_url = "$$$".join(
            "直播$" + cat + "@" + idx + "@" + s for s, _ in lines)
        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": logo,
            "vod_content": name + " · 4GTV 双源直播（单源失效请切换线路）",
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        # id = 分类@序号@线路名
        parts = id.split("@")
        cat, idx, src = parts[0], parts[1], parts[2]
        lines = dict((s, u) for s, u in self._srcs(cat, int(idx)))
        url = lines.get(src) or (lines.get(SRC_4) or lines.get(SRC_Y) or "")
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": {
                "User-Agent": _UA,
                "Referer": "https://www.4gtv.tv/",
            },
        }

    def searchContent(self, key, quick, pg="1"):
        return self._search(key)

    def searchContentPage(self, key, quick, pg="1"):
        return self._search(key)

    def _search(self, key):
        vods = []
        for cat, items in CHANNELS.items():
            for i, (name, logo, _) in enumerate(items):
                if key.lower() in name.lower():
                    vods.append(self._vod(cat, i, name, logo))
        return {"list": vods, "page": 1, "pagecount": 1,
                "limit": len(vods), "total": len(vods)}

    def localProxy(self, param):
        return [200, "image/png", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass
