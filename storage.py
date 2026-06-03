# storage.py — 招聘猫 数据持久化模块
import json
import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from models import Notice

logger = logging.getLogger(__name__)

# 数据默认存放于用户 AppData 目录
APP_DATA_DIR = Path(os.getenv("APPDATA", ".")) / "招聘猫"


def get_data_dir(custom_dir: Optional[str] = None) -> Path:
    d = Path(custom_dir) if custom_dir else APP_DATA_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _site_key(url: str) -> str:
    """将 url 转为合法文件名"""
    url = url.strip().rstrip("/")
    key = re.sub(r"[^\w.-]", "_", url)
    return key[:128]


class Storage:
    """本地 JSON 存储，每个网站独立一个文件"""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = get_data_dir(data_dir)
        logger.info(f"数据目录: {self.data_dir}")

    def _path(self, url: str) -> Path:
        return self.data_dir / f"{_site_key(url)}.json"

    def load(self, url: str) -> List[Notice]:
        """加载某网站的历史通知"""
        p = self._path(url)
        if not p.exists():
            return []
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [Notice.from_dict(d) for d in data.get("notices", [])]
        except Exception as e:
            logger.warning(f"读取存储失败 {p}: {e}")
            return []

    def save(self, url: str, notices: List[Notice]):
        """保存某网站的最新通知"""
        p = self._path(url)
        payload = {
            "url": url,
            "saved_at": datetime.now().isoformat(),
            "notices": [n.to_dict() for n in notices],
        }
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存存储失败 {p}: {e}")

    def load_all_urls(self) -> List[str]:
        """返回所有已存储过的网站列表"""
        urls = []
        for p in self.data_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                urls.append(data.get("url", ""))
            except Exception:
                pass
        return [u for u in urls if u]

    def delete(self, url: str):
        p = self._path(url)
        if p.exists():
            p.unlink()

    def clear_all(self):
        for p in self.data_dir.glob("*.json"):
            p.unlink()
