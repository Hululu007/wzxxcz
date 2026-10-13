/**
 * 燃超影院 aarnadhya.com | WebHTV JS Spider
 * 走 QuickJS 运行时，req() 走 Native OkHttp，能过 Cloudflare
 */
var HOST = "https://www.aarnadhya.com";
var UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
var DEFAULT_PIC = HOST + "/template/m4-drama/images/favicon.svg";

var CLASSES = [
    { type_id: "1",  type_name: "电影" },
    { type_id: "2",  type_name: "电视剧" },
    { type_id: "3",  type_name: "短剧" },
    { type_id: "4",  type_name: "动漫" },
    { type_id: "5",  type_name: "综艺" },
    { type_id: "48", type_name: "网飞新剧" },
    { type_id: "47", type_name: "AI漫剧" }
];

var GENRE_MAP = {
    "1":  ["剧情","喜剧","动作","恐怖","爱情","科幻","惊悚","战争","犯罪","悬疑","奇幻"],
    "2":  ["喜剧","爱情","悬疑","古装","剧情","武侠","都市","仙侠","谍战","战争","奇幻","冒险"],
    "3":  ["现代都市","女频恋爱","古装仙侠","反转爽剧","穿越","逆袭","脑洞悬疑","甜宠","重生","虐恋","现代言情","神豪","悬疑"],
    "4":  ["剧情","奇幻","犯罪","悬疑","惊悚","喜剧","古装","爱情","科幻","动作"],
    "5":  ["古装","剧情","喜剧","动作","都市","爱情","穿越","科幻","逆袭","惊悚","悬疑","犯罪","武侠","谍战","冒险"],
    "48": ["古装","剧情","喜剧","动作","都市","爱情","穿越","科幻","逆袭","惊悚","悬疑","犯罪","武侠","谍战","冒险"],
    "47": ["剧情","奇幻","犯罪","悬疑","惊悚","喜剧","古装","爱情","科幻","动作"]
};

var AREAS = ["大陆","香港","台湾","美国","韩国","日本","欧美","英国","法国","泰国","印度","加拿大","西班牙","德国","俄罗斯","新加坡"];
var YEARS = (function(){ var a=[]; for(var y=2026; y>=2012; y--) a.push(String(y)); return a; })();
var SORTS = [["time","最近更新"],["hits","最多播放"],["score","最高评分"]];

function mk(vals) {
    var out = [{ n: "全部", v: "" }];
    for (var i = 0; i < vals.length; i++) out.push({ n: vals[i], v: vals[i] });
    return out;
}

var FILTERS = {};
for (var ci = 0; ci < CLASSES.length; ci++) {
    var tid = CLASSES[ci].type_id;
    FILTERS[tid] = [
        { key: "class", name: "剧情", value: mk(GENRE_MAP[tid] || []) },
        { key: "area",  name: "地区", value: mk(AREAS) },
        { key: "year",  name: "年份", value: mk(YEARS) },
        { key: "by",    name: "排序", value: (function(){ var o=[{n:"全部",v:""}]; for (var i=0;i<SORTS.length;i++) o.push({n:SORTS[i][1],v:SORTS[i][0]}); return o; })() }
    ];
}

/* ========== 工具 ========== */
function fixUrl(u) {
    if (!u) return "";
    u = String(u).trim();
    if (u.indexOf("//") === 0) return "https:" + u;
    if (u.indexOf("http") === 0) return u;
    if (u.indexOf("/") === 0) return HOST + u;
    return HOST + "/" + u;
}

function clean(s) {
    if (!s) return "";
    return String(s)
        .replace(/<br\s*\/?>/gi, "\n")
        .replace(/<[^>]+>/g, "")
        .replace(/&nbsp;/g, " ").replace(/\u00a0/g, " ")
        .replace(/&amp;/g, "&").replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
        .replace(/[ \t\r\f\v]+/g, " ")
        .replace(/\n{2,}/g, "\n")
        .trim();
}

function request(url, opts) {
    var options = { headers: { "User-Agent": UA, "Referer": url, "Accept-Encoding": "gzip, deflate" }, timeout: 25 };
    if (opts) for (var k in opts) options[k] = opts[k];
    var r = req(url, options);
    if (typeof r === "string") return r;
    if (r && r.content) return r.content;
    return "";
}

/* ========== 卡片解析 ========== */
function extractVideos(html) {
    var videos = [];
    var seen = {};
    if (!html) return videos;

    // a.zj-item
    var re = /<a\s+href="(\/video\/[^"]+\.html)"\s+class="zj-item"[^>]*?title="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi;
    var m;
    while ((m = re.exec(html)) !== null) {
        var href = m[1], title = m[2], inner = m[3];
        if (seen[href]) continue;
        seen[href] = 1;

        var name = clean(title);
        if (!name) {
            var tm = /<div\s+class="zj-item-title[^"]*"[^>]*>([\s\S]*?)<\/div>/i.exec(inner);
            if (tm) name = clean(tm[1]);
        }
        if (!name) name = href.replace(/.*\//, "").replace(".html", "");

        var pic = "";
        var im = /<img[^>]*?src="([^"]*)"/i.exec(inner);
        if (im) pic = fixUrl(im[1]);
        if (!pic) pic = DEFAULT_PIC;

        var remark = "";
        var cm = /<div\s+class="zj-corner[^"]*"[^>]*title="([^"]*)"/i.exec(inner);
        if (cm) remark = clean(cm[1]);

        videos.push({ vod_id: href, vod_name: name.substring(0,100), vod_pic: pic, vod_remarks: remark });
    }

    // banner 兜底
    if (videos.length === 0) {
        var bre = /<a\s+href="(\/video\/[^"]+\.html)"\s+class="zj-banner"[^>]*?title="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi;
        while ((m = bre.exec(html)) !== null) {
            var bh = m[1], bt = m[2], bi = m[3];
            if (seen[bh]) continue;
            seen[bh] = 1;
            var bn = clean(bt);
            var bp = "";
            var bim = /<img[^>]*?src="([^"]*)"/i.exec(bi);
            if (bim) bp = fixUrl(bim[1]);
            if (!bp) bp = DEFAULT_PIC;
            videos.push({ vod_id: bh, vod_name: bn.substring(0,100), vod_pic: bp, vod_remarks: "" });
        }
    }

    return videos;
}

function pageCount(html, current) {
    if (!html) return current || 1;
    var re = /href="\/tv\/\d+\/[^"]*?page\/(\d+)/gi;
    var mx = current || 1, m;
    while ((m = re.exec(html)) !== null) {
        var n = parseInt(m[1], 10);
        if (n > mx) mx = n;
    }
    if (mx > (current || 1)) return mx;
    var s = /<span>\d+\/(\d+)<\/span>/i.exec(html);
    if (s) { var p = parseInt(s[1], 10); if (p) return p; }
    return current || 1;
}

/* ========== Spider API ========== */
var spider = {
    init: function(ext) {
        try { if (ext && typeof ext === "object" && ext.site) HOST = String(ext.site).replace(/\/$/, ""); } catch(e) {}
    },

    home: function(filter) {
        return JSON.stringify({ class: CLASSES, filters: FILTERS });
    },

    homeVod: function() {
        var html = request(HOST + "/");
        return JSON.stringify({ list: extractVideos(html) });
    },

    category: function(tid, pg, filter, extend) {
        var page = parseInt(pg || "1", 10); if (isNaN(page) || page < 1) page = 1;
        extend = extend || {};

        // 清空值
        for (var k in extend) {
            if (extend[k] === "" || extend[k] === null || extend[k] === "全部") delete extend[k];
        }

        // 站点真实拼接顺序：class → area → lang → page → year → by
        var seg = [];
        if (extend["class"]) seg.push("class/" + encodeURIComponent(extend["class"]));
        if (extend["area"])  seg.push("area/"  + encodeURIComponent(extend["area"]));
        if (extend["lang"])  seg.push("lang/"  + encodeURIComponent(extend["lang"]));
        if (page > 1)        seg.push("page/"  + page);
        if (extend["year"])  seg.push("year/"  + extend["year"]);
        if (extend["by"])    seg.push("by/"    + extend["by"]);

        var url;
        if (seg.length > 0) {
            url = HOST + "/tv/" + tid + "/" + seg.join("/") + ".html";
        } else {
            url = HOST + "/tv/" + tid + ".html";
        }

        var html = request(url);
        var videos = extractVideos(html);
        var pc = pageCount(html, page);

        return JSON.stringify({
            list: videos, page: page, pagecount: pc,
            limit: 36, total: pc * 36
        });
    },

    search: function(key, quick, pg) {
        var page = parseInt(pg || "1", 10); if (isNaN(page) || page < 1) page = 1;
        var url = HOST + "/search.html?wd=" + encodeURIComponent(key);
        if (page > 1) url += "&page=" + page;

        var html = request(url);
        var videos = extractVideos(html);
        return JSON.stringify({
            list: videos, page: page, pagecount: pageCount(html, page),
            limit: 36, total: 999
        });
    },

    detail: function(id) {
        var url = id.indexOf("http") === 0 ? id : fixUrl(id);
        var html = request(url);
        if (!html) return JSON.stringify({ list: [] });

        var name = "";
        var h1 = /<h1[^>]*>([\s\S]*?)<small/i.exec(html);
        if (h1) name = clean(h1[1]);
        if (!name) {
            var t = /<title>(.*?)<\/title>/i.exec(html);
            if (t) name = clean(t[1].split("_")[0].split("-")[0]);
        }
        if (!name) name = id;

        var pic = DEFAULT_PIC;
        var p = /<div\s+class="zj-detail-cover">\s*<img[^>]*?src="([^"]*)"/i.exec(html);
        if (p) pic = fixUrl(p[1]);

        var director = "", actor = "";
        var d = /导演：<b>([^<]*)<\/b>/i.exec(html);
        if (d) director = clean(d[1]);
        var a = /主演：<b>([^<]*)<\/b>/i.exec(html);
        if (a) actor = clean(a[1]);

        var score = "";
        var sc = /<span\s+class="zj-rating-num">([\d.]+)<\/span>/i.exec(html);
        if (sc) score = sc[1];

        var content = "";
        var de = /<p\s+class="zj-desc[^"]*">([\s\S]*?)<\/p>/i.exec(html);
        if (de) content = clean(de[1]);
        if (!content) {
            var md = /<meta[^>]*name="description"[^>]*content="([^"]*)"/i.exec(html);
            if (md) content = clean(md[1]);
        }
        content = content ? ("🍊小橙子提醒您：请勿相信视频中的广告！\n" + content) : "🍊小橙子提醒您：请勿相信视频中的广告！";

        // 线路名
        var lineNames = {};
        var lre = /<button\s+class="zj-line-btn[^"]*"\s+type="button"\s+data-sid="(\d+)"[^>]*>([^<]*)<\/button>/gi, lm;
        while ((lm = lre.exec(html)) !== null) {
            lineNames[lm[1]] = clean(lm[2]) || ("线路" + lm[1]);
        }

        // 剧集面板
        var groups = {};
        var pre = /<div\s+class="zj-eps\s+zj-eps-panel[^"]*"\s+data-sid="(\d+)"[^>]*>([\s\S]*?)<\/div>/gi, pm;
        while ((pm = pre.exec(html)) !== null) {
            var sid = pm[1], block = pm[2], eps = [];
            var ere = /<a\s+href="(\/play\/[^"]+\.html)"\s+class="zj-ep[^"]*"\s+title="([^"]*)"[^>]*>([^<]*)<\/a>/gi, em;
            while ((em = ere.exec(block)) !== null) {
                var href = em[1];
                if (href.indexOf("/") === 0) href = HOST + href;
                var title = clean(em[2]) || clean(em[3]) || ("第" + (eps.length + 1) + "集");
                eps.push({ name: title, url: href });
            }
            if (eps.length > 0) groups[sid] = eps;
        }

        if (Object.keys(groups).length === 0) return JSON.stringify({ list: [] });

        var order = [];
        for (var sid in lineNames) order.push(sid);
        for (var sid2 in groups) if (order.indexOf(sid2) < 0) order.push(sid2);

        var playFrom = [], playUrl = [];
        for (var i = 0; i < order.length; i++) {
            var s = order[i];
            if (!groups[s]) continue;
            playFrom.push(lineNames[s] || ("线路" + s));
            var arr = [];
            for (var j = 0; j < groups[s].length; j++) {
                arr.push(groups[s][j].name + "$" + groups[s][j].url);
            }
            playUrl.push(arr.join("#"));
        }

        return JSON.stringify({ list: [{
            vod_id: id,
            vod_name: name,
            vod_pic: pic,
            vod_content: content,
            vod_actor: actor,
            vod_director: director,
            vod_score: score,
            vod_remarks: playFrom.length + "条线路",
            vod_play_from: playFrom.join("$$$"),
            vod_play_url: playUrl.join("$$$")
        }]});
    },

    play: function(flag, id, flags) {
        var url = id.indexOf("http") === 0 ? id : fixUrl(id);
        var html = request(url);

        var realUrl = "";
        var pm = /var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*<\/script>/i.exec(html);
        if (pm) {
            var um = /"url"\s*:\s*"([^"]+)"/i.exec(pm[1]);
            if (um) realUrl = um[1].replace(/\\\//g, "/").replace(/&amp;/g, "&");
        }

        if (realUrl) {
            return JSON.stringify({
                parse: 0,
                playUrl: "",
                url: realUrl,
                header: { "User-Agent": UA, "Referer": HOST + "/" }
            });
        }

        return JSON.stringify({
            parse: 1,
            playUrl: "",
            url: url,
            header: { "User-Agent": UA, "Referer": HOST + "/" }
        });
    }
};

/* 标准导出 */
export default spider;

/* 兼容旧运行时 */
function __jsEvalReturn() { return spider; }