# scraper.py — 招聘猫 网页抓取模块
import re
import time
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse
from typing import List, Optional

import requests
import urllib3
from bs4 import BeautifulSoup

from models import Notice, RECRUIT_KEYWORDS, DATE_PATTERNS

logger = logging.getLogger(__name__)

# 政府网站常使用自签名证书，需关闭 SSL 校验和警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

REQUEST_TIMEOUT = 20   # 秒
MAX_NOTICES_PER_SITE = 200


def _is_recruit_text(text: str) -> bool:
    """判断文本是否与招聘相关"""
    text_lower = text.lower()
    return any(kw in text_lower for kw in RECRUIT_KEYWORDS)


def _extract_date(text: str) -> str:
    """从文本中提取日期"""
    for pattern in DATE_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return m.group(0).strip("()")
    return ""


def _clean_text(text: str) -> str:
    """清理多余空白"""
    return re.sub(r"\s+", " ", text).strip()


def _get_encoding(response: requests.Response) -> str:
    """推断正确的编码"""
    if response.encoding and response.encoding.lower() not in ("iso-8859-1", "windows-1252"):
        return response.encoding
    # 从 meta 标签猜测
    sniff = response.content[:4096].decode("latin-1", errors="ignore").lower()
    m = re.search(r'charset=["\']?([\w-]+)', sniff)
    if m:
        return m.group(1)
    return "utf-8"


class WebScraper:
    """通用招聘通知抓取器"""

    def __init__(self, timeout: int = REQUEST_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.verify = False   # 部分政府网站证书有问题

    def scrape(self, url: str) -> List[Notice]:
        """抓取指定网址的招聘通知列表"""
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.exceptions.SSLError:
            # 降级到 http
            url = url.replace("https://", "http://")
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()

        encoding = _get_encoding(resp)
        html = resp.content.decode(encoding, errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        notices = self._extract_notices(soup, url)
        logger.info(f"[{url}] 抓取到 {len(notices)} 条通知")
        return notices[:MAX_NOTICES_PER_SITE]

    # ------------------------------------------------------------------
    # 内部提取逻辑
    # ------------------------------------------------------------------

    def _extract_notices(self, soup: BeautifulSoup, base_url: str) -> List[Notice]:
        """从页面 DOM 中提取招聘通知"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notices: List[Notice] = []
        seen_hashes: set = set()

        # 策略1：找带招聘关键词的 <a> 标签
        for a in soup.find_all("a", href=True):
            title = _clean_text(a.get_text())
            if not title or not _is_recruit_text(title):
                continue
            if len(title) < 4 or len(title) > 200:
                continue

            href = a["href"].strip()
            if href.startswith(("javascript:", "#", "mailto:", "tel:")):
                continue
            link = urljoin(base_url, href)

            # 尝试在父元素中找日期
            date = ""
            parent = a.parent
            for _ in range(3):
                if parent is None:
                    break
                parent_text = _clean_text(parent.get_text())
                date = _extract_date(parent_text)
                if date:
                    break
                parent = parent.parent

            snippet = _extract_snippet(a)

            notice = Notice(
                title=title,
                link=link,
                date=date,
                snippet=snippet,
                source_url=base_url,
                scraped_at=now_str,
            )
            if notice.content_hash not in seen_hashes:
                seen_hashes.add(notice.content_hash)
                notices.append(notice)

        # 策略2：若策略1无收获，退化为抓取页面所有链接（含日期的优先）
        if not notices:
            for a in soup.find_all("a", href=True):
                title = _clean_text(a.get_text())
                if not title or len(title) < 4 or len(title) > 200:
                    continue
                href = a["href"].strip()
                if href.startswith(("javascript:", "#", "mailto:", "tel:")):
                    continue
                link = urljoin(base_url, href)
                date = _extract_date(_clean_text(a.parent.get_text() if a.parent else ""))
                if not date:
                    continue   # 退化模式只保留有日期的条目

                notice = Notice(
                    title=title,
                    link=link,
                    date=date,
                    snippet="",
                    source_url=base_url,
                    scraped_at=now_str,
                )
                if notice.content_hash not in seen_hashes:
                    seen_hashes.add(notice.content_hash)
                    notices.append(notice)

        # 按日期倒排（有日期的排前面）
        notices.sort(key=lambda n: n.date, reverse=True)
        return notices


def _extract_snippet(tag) -> str:
    """提取链接附近的摘要文字"""
    try:
        parent = tag.parent
        if parent:
            return _clean_text(parent.get_text())[:120]
    except Exception:
        pass
    return ""
