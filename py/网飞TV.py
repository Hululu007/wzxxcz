# coding=utf-8
"""
网飞TV wangfei.tv | TVBox Python 爬虫 (小橙子特供版 V10.0 终极杀 Boss 版)
关键:
  - 破解分类页假 ID 陷阱 (自动探测 22/31 等真实子类)
  - 破解 GFI 裂图陷阱 (强力补全缺失的 HTTP 协议和根路径，完美兜底)
  - 简介前缀保留，完全对齐豆花风格
  - 解析 JSON-LD 获取 m3u8 直链 (极速线路秒播)
  - 彻底干掉外挂跳转，极简清爽
"""
import ast
import base64
import html as html_module
import json
import re
import time
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        """Small fallback used by offline tests outside TVBox."""
        def __init__(self):
            pass
        def getProxyUrl(self):
            return ""


class Spider(BaseSpider):
    DEFAULT_HOST = "https://www.wangfei.tv"
    DEFAULT_UA = (
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
    )
    CLASSES = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "电视剧", "type_id": "2"},
        {"type_name": "综艺", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
        {"type_name": "纪录片", "type_id": "5"},
        {"type_name": "短剧", "type_id": "47"},
    ]
    
    # 豆花风格前缀
    INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"
    
    MEDIA_EXTENSIONS = (
        ".m3u8", ".mp4", ".mkv", ".flv", ".ts", ".webm", ".avi", ".mov"
    )
    PLAY_PATH_RE = re.compile(
        r"/(?:vodplay|play)/[^\"'?#<>\s]+|/vod-play-[^\"'?#<>\s]+",
        re.I,
    )
    DETAIL_PATH_RE = re.compile(r"/voddetail/[^\"'?#<>\s]+\.html", re.I)
    CF_SIGNS = (
        "just a moment", "checking your browser",
        "attention required! | cloudflare",
    )
    CF_SOFT_SIGNS = ("challenge-platform", "cf-chl-", "cf_chl_")
    CONTENT_SIGNS = (
        "/voddetail/", "/vodplay/", "player_aaaa", ".m3u8",
        "module-poster", "module-info", "module-play-list",
        "anthology-list", "playlist",
    )
    AD_KEYWORDS = (
        "/ad/", "/ads/", "advert", "commercial", "promotion", "_ad_",
        "/gg/", "/gg", "-ad-", "adsegment", "adservice",
    )

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.host = self.DEFAULT_HOST
        self.ua = self.DEFAULT_UA
        self.cookie = ""
        self.timeout = 15
        self.use_cffi = False
        self.proxy_enabled = False
        self.session = requests.Session()
        self.headers = {}
        self._refresh_headers()

    def init(self, extend=""):
        config = self._parse_extend(extend)
        self.host = str(config.get("host") or self.DEFAULT_HOST).strip().rstrip("/")
        self.ua = str(config.get("ua") or self.DEFAULT_UA).strip()
        self.cookie = str(config.get("cookie") or "").strip()
        self.timeout = self._safe_int(config.get("timeout"), 15, 5, 60)
        self.use_cffi = self._as_bool(config.get("use_cffi"), False)
        self.proxy_enabled = self._as_bool(config.get("proxy"), False)
        self.session = requests.Session()
        self._refresh_headers()
        return True

    def getName(self):
        return "网飞TV"

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    @staticmethod
    def _safe_int(value, default, minimum=None, maximum=None):
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        if minimum is not None: number = max(minimum, number)
        if maximum is not None: number = min(maximum, number)
        return number

    @staticmethod
    def _as_bool(value, default=False):
        if value is None: return default
        if isinstance(value, bool): return value
        return str(value).strip().lower() in {"1", "true", "yes", "on", "y", "开启", "是"}

    def _parse_extend(self, extend):
        if isinstance(extend, dict): return dict(extend)
        if not extend: return {}
        text = str(extend).strip()
        try:
            value = json.loads(text)
            return value if isinstance(value, dict) else {}
        except Exception:
            pass
        try:
            parsed = parse_qs(text, keep_blank_values=True)
            return {key: values[-1] for key, values in parsed.items()}
        except Exception:
            return {}

    def _refresh_headers(self):
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        if self.cookie:
            self.headers["Cookie"] = self.cookie
        self.session.headers.clear()
        self.session.headers.update(self.headers)

    def _request_headers(self, referer="", accept=""):
        headers = dict(self.headers)
        if referer: headers["Referer"] = referer
        if accept: headers["Accept"] = accept
        return headers

    @classmethod
    def _is_cloudflare_text(cls, text):
        lower = (text or "")[:100000].lower()
        if any(sign in lower for sign in cls.CF_SIGNS): return True
        if not any(sign in lower for sign in cls.CF_SOFT_SIGNS): return False
        return not any(sign in lower for sign in cls.CONTENT_SIGNS)

    def _blocked_response(self, response, text=""):
        if response is None: return True
        if getattr(response, "status_code", 0) in (401, 403, 429, 503): return True
        return self._is_cloudflare_text(text)

    def _request_raw(self, url, referer="", binary=False):
        if not url: return None
        target = self._absolute(url, referer or self.host)
        headers = self._request_headers(referer, "*/*" if binary else "text/html,application/xhtml+xml,*/*;q=0.8")
        response = None
        text = ""
        for attempt in range(2):
            try:
                response = self.session.get(target, headers=headers, timeout=self.timeout, allow_redirects=True)
                if not binary:
                    response.encoding = response.apparent_encoding or "utf-8"
                    text = response.text
                if not self._blocked_response(response, text): return response
                break
            except Exception:
                response = None
                if attempt == 0: time.sleep(0.25)

        if self.use_cffi and cffi_requests is not None:
            try:
                response = cffi_requests.get(target, headers=headers, timeout=self.timeout, allow_redirects=True, impersonate="chrome131")
                if not binary:
                    response.encoding = getattr(response, "apparent_encoding", None) or "utf-8"
                    text = response.text
                if not self._blocked_response(response, text): return response
            except Exception:
                return None
        return None

    def _get_text(self, url, referer=""):
        response = self._request_raw(url, referer=referer, binary=False)
        if response is None: return ""
        try:
            text = response.text or ""
            return "" if self._is_cloudflare_text(text) else text
        except Exception:
            return ""

    @staticmethod
    def _absolute(url, base):
        if not url: return ""
        value = html_module.unescape(str(url).strip()).replace("\\/", "/")
        if value.startswith("//"): return (urlparse(base).scheme or "https") + ":" + value
        # 陷阱修补：如果图片是相对路径且没有开头斜杠
        if not value.startswith("http") and not value.startswith("/"):
            value = "/" + value
        return urljoin(base, value)

    @staticmethod
    def _clean_text(value):
        if value is None: return ""
        text = html_module.unescape(str(value)).replace("\xa0", " ")
        text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip(" \t\r\n/|\u00b7")

    @staticmethod
    def _safe_label(value, fallback="线路"):
        label = Spider._clean_text(value) or fallback
        return label.replace("$", "_").replace("#", "_")[:80]

    @staticmethod
    def _attr_first(node, names):
        if node is None: return ""
        for name in names:
            value = node.get(name)
            if value and not str(value).lower().startswith("data:image"):
                return str(value).strip()
        return ""

    def _first_text(self, node, selectors):
        if node is None or not hasattr(node, "select_one"): return ""
        for selector in selectors:
            found = node.select_one(selector)
            if found:
                text = self._clean_text(found.get_text(" ", strip=True))
                if text: return text
        return ""

    def _log(self, message):
        try: print(f"[网飞TV] {message}")
        except Exception: pass

    def homeContent(self, filter=False):
        return {"class": list(self.CLASSES), "filters": {}}

    def homeVideoContent(self):
        source = self._get_text(self.host + "/", referer=self.host + "/")
        return {"list": self._parse_video_list(source, self.host)[:80]}

    def _parse_video_list(self, source, page_url=""):
        if not source: return []
        if BeautifulSoup is None:
            return self._parse_video_list_regex(source, page_url)

        soup = BeautifulSoup(source, "html.parser")
        records = {}
        order = []
        for anchor in soup.select('a[href*="/voddetail/"]'):
            href = anchor.get("href", "")
            if not self.DETAIL_PATH_RE.search(href): continue
            absolute = self._absolute(href, page_url or self.host)
            path_match = self.DETAIL_PATH_RE.search(urlparse(absolute).path)
            vod_id = path_match.group(0) if path_match else absolute
            image = anchor.find("img")
            title = (
                anchor.get("title")
                or self._attr_first(image, ("alt", "title"))
                or self._first_text(anchor, (
                    ".module-item-title", ".module-poster-item-title", ".video-name",
                    ".vod-name", ".title", "h3", "h4", "strong",
                ))
            )
            title = self._clean_text(title)
            if title.lower() in {"play", "detail", "more"}: title = ""
            
            # 图片兜底：如果扒出来的图有问题，直接换默认图
            pic = self._attr_first(image, ("data-original", "data-src", "data-lazy", "data-echo", "src"))
            pic = self._absolute(pic, page_url or self.host) if pic else ""
            if not pic or not pic.startswith("http"):
                pic = "https://www.wangfei.tv/upload/vod/20251211-1/569089b2bfc36db5559b19b6db5e9d8c.jpg"

            card = anchor
            for _ in range(4):
                if card is None: break
                classes = " ".join(card.get("class", [])) if hasattr(card, "get") else ""
                if re.search(r"item|card|list|module|poster|video", classes, re.I): break
                card = card.parent
                
            remarks = self._first_text(card, (
                ".module-item-note", ".module-poster-item-info", ".pic-text",
                ".video-serial", ".remarks", ".remark", ".note", ".hdtag",
                ".text-right", ".module-item-caption", ".module-item-text",
            ))

            record = records.get(vod_id)
            if record is None:
                record = {
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": self._clean_text(remarks),
                }
                records[vod_id] = record
                order.append(vod_id)
            else:
                if not record["vod_name"] and title: record["vod_name"] = title
                if not record["vod_pic"] and pic: record["vod_pic"] = pic
                if not record["vod_remarks"] and remarks: record["vod_remarks"] = self._clean_text(remarks)
        return [records[key] for key in order if records[key].get("vod_name")]

    def _parse_video_list_regex(self, source, page_url):
        records, seen = [], set()
        pattern = re.compile(r"<a\b([^>]*href=[\"']([^\"']*/voddetail/[^\"']+\.html)[\"'][^>]*)>", re.I)
        for match in pattern.finditer(source):
            href = match.group(2)
            path_match = self.DETAIL_PATH_RE.search(href)
            vod_id = path_match.group(0) if path_match else href
            if vod_id in seen: continue
            seen.add(vod_id)
            snippet = source[match.start():match.start() + 1600]
            title_match = re.search(r"(?:title|alt)=[\"']([^\"']+)[\"']", snippet, re.I)
            pic_match = re.search(r"(?:data-original|data-src|data-lazy|data-echo|src)=[\"']([^\"']+)[\"']", snippet, re.I)
            title = self._clean_text(title_match.group(1) if title_match else "")
            if not title: continue
            
            pic = self._absolute(pic_match.group(1), page_url or self.host) if pic_match else ""
            if not pic or not pic.startswith("http"):
                pic = "https://www.wangfei.tv/upload/vod/20251211-1/569089b2bfc36db5559b19b6db5e9d8c.jpg"
                
            records.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return records

    def _parse_pagecount(self, source, current_page):
        if not source: return current_page
        values = [int(value) for value in re.findall(r"/page/(\d+)", source)]
        values += [int(value) for value in re.findall(r"[?&]page=(\d+)", source)]
        total_match = re.search(r"共\s*(\d+)\s*页", self._clean_text(source))
        if total_match: values.append(int(total_match.group(1)))
        return max(values + [current_page + 1])

    def _fetch_first_list(self, paths, reject_home=False):
        last_source = ""
        for path in paths:
            url = self._absolute(path, self.host)
            self._log(f"尝试请求: {url}")
            source = self._get_text(url, referer=self.host + "/")
            if source:
                last_source = source
                if reject_home and "search" in url.lower(): continue
                videos = self._parse_video_list(source, url)
                if videos:
                    self._log(f"-> 成功抓取 {len(videos)} 条数据")
                    return videos, source
        return [], last_source

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = self._safe_int(pg, 1, 1)
        tid = str(tid or "1")
        
        # 陷阱修补：如果传进来是大类，追加真实子类 ID
        ids_to_try = [tid]
        if tid == "2": ids_to_try.extend(["22", "23", "24", "25", "28", "31"])
        elif tid == "1": ids_to_try.extend(["9", "10", "11", "12"])
        
        all_videos = []
        source = ""
        for _id in ids_to_try:
            if page == 1:
                paths = [f"/vodshow/id/{_id}.html", f"/vodtype/{_id}.html"]
            else:
                paths = [
                    f"/vodshow/id/{_id}/page/{page}.html",
                    f"/vodshow/page/{page}/id/{_id}.html",
                ]
            videos, src = self._fetch_first_list(paths)
            if videos:
                all_videos = videos
                source = src
                break

        pagecount = self._parse_pagecount(source, page) if all_videos else page
        return {
            "list": all_videos,
            "page": page,
            "pagecount": pagecount,
            "limit": len(all_videos),
            "total": pagecount * max(len(all_videos), 1),
        }

    def searchContent(self, key, quick, pg="1"):
        page = self._safe_int(pg, 1, 1)
        keyword = quote(unquote(str(key or "").strip()), safe="")
        if not keyword:
            return {"list": [], "page": page, "pagecount": page, "limit": 0, "total": 0}
        current = f"/vod/search?wd={keyword}"
        if page > 1: current += f"&page={page}"
        rewritten = f"/vodsearch/wd/{keyword}.html"
        paths = [current, rewritten]
        videos, source = self._fetch_first_list(paths, reject_home=True)
        pagecount = self._parse_pagecount(source, page) if videos else page
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos),
            "total": pagecount * max(len(videos), 1),
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        raw_id = str(raw_id or "").strip()
        if not raw_id: return {"list": []}
        if raw_id.isdigit(): raw_id = f"/voddetail/{raw_id}.html"
        detail_url = self._absolute(raw_id, self.host)
        source = self._get_text(detail_url, referer=self.host + "/")
        
        metadata = self._parse_detail_metadata(source, detail_url)
        
        # ========== 核心 Boss 斩杀：只留极速线路，干掉外挂 ==========
        lines = []
        
        # 1. 从 JSON-LD 中提取最高清 m3u8 直链
        for j_str in re.findall(r'<script type="application/ld\+json">(.*?)</script>', source, re.S):
            try:
                j_data = json.loads(j_str)
                if isinstance(j_data, dict) and j_data.get("@type") == "VideoObject":
                    c_url = j_data.get("contentUrl")
                    if c_url and ".m3u8" in c_url:
                        lines.append(("极速线路", "第1集$" + c_url))
                        self._log("发现隐藏极速M3U8")
                        break
            except Exception: pass

        # 兜底：传统的提取方式
        if not lines:
            line_links = self._extract_line_links(source, detail_url)
            lines = self._fetch_provider_lines(line_links, detail_url)

        metadata.update({
            "vod_id": raw_id,
            "vod_play_from": "$$$".join(item[0] for item in lines) if lines else "未知",
            "vod_play_url": "$$$".join(item[1] for item in lines) if lines else "",
        })
        
        if not lines:
            self._log("❌ 详情页解析失败：未找到任何线路")
            
        return {"list": [metadata]}

    def _parse_detail_metadata(self, source, detail_url):
        result = {"vod_name": "未知影片", "vod_pic": "", "type_name": "", "vod_year": "", "vod_area": "", "vod_remarks": "", "vod_actor": "", "vod_director": "", "vod_content": ""}
        if not source: return result

        if BeautifulSoup is None:
            title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", source, re.I | re.S)
            if title_match: result["vod_name"] = self._clean_text(title_match.group(1))
            return result

        soup = BeautifulSoup(source, "html.parser")
        title_node = soup.select_one(".module-info-heading h1, h1")
        if title_node: result["vod_name"] = self._clean_text(title_node.get_text(" ", strip=True))

        pic_node = soup.select_one('meta[property="og:image"]')
        if pic_node: result["vod_pic"] = self._absolute(pic_node.get("content", ""), detail_url)

        labels = self._extract_detail_labels(soup)
        result["type_name"] = labels.get("类型", "")
        result["vod_year"] = labels.get("年份", "")
        result["vod_area"] = labels.get("地区", "")
        result["vod_actor"] = labels.get("主演", "")
        result["vod_director"] = labels.get("导演", "")
        
        content = self._first_text(soup, (".module-info-introduction-content", "[class*='introduction']"))
        if not content:
            meta_desc = soup.select_one('meta[name="description"]')
            if meta_desc: content = self._clean_text(meta_desc.get("content", ""))
            
        # 豆花风格前缀注入
        if content: result["vod_content"] = self.INTRO_PREFIX + "\n" + content
        else: result["vod_content"] = self.INTRO_PREFIX
        
        return result

    def _extract_detail_labels(self, soup):
        labels = {}
        wanted = {"类型", "分类", "年份", "地区", "主演", "导演", "进度", "状态"}
        for text in soup.stripped_strings:
            cleaned = self._clean_text(text)
            match = re.match(r"^([^\uff1a:]{1,8})[\uff1a:]\s*(.+)$", cleaned)
            if match and match.group(1).strip() in wanted:
                if match.group(1).strip() not in labels:
                    labels[match.group(1).strip()] = self._clean_text(match.group(2))
        return labels

    def _extract_line_links(self, source, detail_url):
        if not source or BeautifulSoup is None: return []
        soup = BeautifulSoup(source, "html.parser")
        candidates = []
        for anchor in soup.find_all("a", href=True):
            text = self._clean_text(anchor.get_text(" ", strip=True))
            if not re.search(r"(线路|路线|在线|云播|播放源)", text): continue
            absolute = self._absolute(anchor.get("href", ""), detail_url)
            if absolute != detail_url: candidates.append((self._safe_label(text), absolute))
        return candidates[:30]

    def _fetch_provider_lines(self, line_links, detail_url):
        for main_label, provider_url in line_links:
            groups = self._parse_provider_detail(main_label, provider_url, detail_url)
            if groups: return groups
        return []

    def _parse_provider_detail(self, main_label, provider_url, detail_url):
        if self.PLAY_PATH_RE.search(urlparse(provider_url).path): return [(main_label, f"播放${provider_url}")]
        source = self._get_text(provider_url, referer=detail_url)
        if not source or BeautifulSoup is None: return []
        
        soup = BeautifulSoup(source, "html.parser")
        anchors = [a for a in soup.find_all("a", href=True) if self.PLAY_PATH_RE.search(a.get("href", ""))]
        if not anchors: return []
        
        eps = []
        seen = set()
        for anchor in anchors:
            absolute = self._absolute(anchor.get("href", ""), provider_url)
            if absolute in seen: continue
            seen.add(absolute)
            name = self._clean_text(anchor.get_text(" ", strip=True) or anchor.get("title"))
            eps.append(f"{self._safe_label(name, '播放')}${absolute}")
        return [(main_label, "#".join(eps))] if eps else []

    def playerContent(self, flag, id, vipFlags=None):
        play_url = self._absolute(str(id or ""), self.host)
        
        # 极速通道直接放行
        if self._is_media_url(play_url):
            return {"parse": 0, "jx": 0, "url": play_url, "header": self._play_headers(play_url)}
            
        # 外挂通道交给嗅探
        if "xyz" in play_url and "voddetail" in play_url:
            return {"parse": 1, "jx": 0, "url": play_url, "header": self._play_headers(play_url)}

        source = self._get_text(play_url, referer=self.host + "/")
        if not source: return {"parse": 1, "jx": 0, "url": play_url, "header": self._play_headers(play_url)}

        config_urls = []
        for variable in ("player_aaaa", "player_data", "MacPlayer"):
            config = self._extract_js_object(source, variable)
            if not config: continue
            raw_url = self._find_url_in_config(config)
            decoded = self._decode_player_url(raw_url, config.get("encrypt"), play_url)
            if decoded:
                config_urls.append(decoded)
                if self._is_media_url(decoded): return self._direct_result(decoded, self._play_headers(play_url))

        direct = self._extract_direct_media(source, play_url)
        if direct: return self._direct_result(direct, self._play_headers(play_url))

        iframe = self._extract_iframe(source, play_url)
        if iframe: return {"parse": 1, "jx": 0, "url": iframe, "header": self._play_headers(play_url)}

        for candidate in config_urls:
            if candidate.startswith("http"): return {"parse": 1, "jx": 0, "url": candidate, "header": self._play_headers(play_url)}
        return {"parse": 1, "jx": 0, "url": play_url, "header": self._play_headers(play_url)}

    def _play_headers(self, referer):
        headers = {"User-Agent": self.ua, "Referer": referer}
        if self.cookie: headers["Cookie"] = self.cookie
        return headers

    def _direct_result(self, media_url, headers):
        final_url = media_url
        if self.proxy_enabled and ".m3u8" in media_url.lower():
            proxied = self._proxy_url(media_url, headers.get("Referer", ""), "m3u8")
            if proxied:
                final_url = proxied
                headers = {}
        return {"parse": 0, "jx": 0, "url": final_url, "header": headers}

    @classmethod
    def _is_media_url(cls, value):
        if not value: return False
        lower = html_module.unescape(str(value)).lower()
        return lower.startswith(("http://", "https://")) and any(ext in lower for ext in cls.MEDIA_EXTENSIONS)

    def _extract_js_object(self, source, variable):
        match = re.search(rf"(?:var\s+|let\s+|const\s+|window\.)?{re.escape(variable)}\s*=\s*", source, re.I)
        if not match: return {}
        start = source.find("{", match.end())
        if start < 0: return {}
        depth, quote_char, escaped = 0, "", False
        for index in range(start, min(len(source), start + 200000)):
            char = source[index]
            if quote_char:
                if escaped: escaped = False
                elif char == "\\": escaped = True
                elif char == quote_char: quote_char = ""
                continue
            if char in ("'", '"'): quote_char = char
            elif char == "{": depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    text = source[start:index + 1]
                    try:
                        value = json.loads(text)
                        return value if isinstance(value, dict) else {}
                    except Exception:
                        try:
                            value = ast.literal_eval(text)
                            return value if isinstance(value, dict) else {}
                        except Exception: return {}
        return {}

    def _find_url_in_config(self, config):
        for key in ("url", "play_url", "playUrl", "src", "m3u8"):
            value = config.get(key)
            if value: return str(value)
        for value in config.values():
            if isinstance(value, dict):
                nested = self._find_url_in_config(value)
                if nested: return nested
        return ""

    def _decode_player_url(self, raw_url, encrypt, page_url):
        if raw_url is None: return ""
        raw = html_module.unescape(str(raw_url)).replace("\\/", "/").strip()
        candidates = [raw]
        try: mode = int(encrypt or 0)
        except Exception: mode = 0
        if mode == 1: candidates.insert(0, unquote(raw))
        elif mode == 2:
            decoded = self._decode_base64(raw)
            if decoded: candidates.insert(0, unquote(decoded))
        else:
            unquoted = unquote(raw)
            if unquoted != raw: candidates.insert(0, unquoted)
            decoded = self._decode_base64(raw)
            if decoded: candidates.insert(0, unquote(decoded))
        for candidate in candidates:
            candidate = html_module.unescape(candidate).replace("\\/", "/").strip()
            if candidate.startswith(("http://", "https://", "//", "/")):
                return self._absolute(candidate, page_url)
        return ""

    @staticmethod
    def _decode_base64(value):
        text = str(value).strip()
        if not text or not re.fullmatch(r"[A-Za-z0-9_+/=-]+", text): return ""
        try:
            padded = text + "=" * (-len(text) % 4)
            return base64.urlsafe_b64decode(padded.encode()).decode("utf-8", "ignore")
        except Exception: return ""

    def _extract_direct_media(self, source, page_url):
        text = html_module.unescape(source).replace("\\/", "/")
        text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda match: chr(int(match.group(1), 16)), text)
        patterns = (r"https?://[^\"'<>\s]+?\.m3u8(?:\?[^\"'<>\s]*)?", r"https?://[^\"'<>\s]+?\.(?:mp4|flv|mkv|webm)(?:\?[^\"'<>\s]*)?")
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match: return self._absolute(match.group(0), page_url)
        return ""

    def _extract_iframe(self, source, page_url):
        match = re.search(r"<iframe\b[^>]*src=[\"']([^\"']+)[\"']", source, re.I)
        return self._absolute(match.group(1), page_url) if match else ""

    def _proxy_url(self, real_url, referer, mode):
        try: base = self.getProxyUrl()
        except Exception: base = ""
        if not base: return ""
        separator = "&" if "?" in base else "?"
        params = {"mode": mode, "url": self._b64_encode(real_url), "ref": self._b64_encode(referer or real_url)}
        query = "&".join(f"{key}={quote(value, safe='')}" for key, value in params.items())
        return base + separator + query

    @staticmethod
    def _b64_encode(value):
        return base64.urlsafe_b64encode(str(value).encode()).decode().rstrip("=")

    @staticmethod
    def _b64_decode(value):
        try: return base64.urlsafe_b64decode(str(value or "") + "=" * (-len(str(value)) % 4)).decode()
        except Exception: return ""

    def localProxy(self, param): return [200, "text/plain", b"", ""]
    def isVideoFormat(self, url): return self._is_media_url(url)
    def manualVideoCheck(self): return False
