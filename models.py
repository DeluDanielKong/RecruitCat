# models.py — 招聘猫 数据模型
from dataclasses import dataclass, field, asdict
from typing import Optional, List
import hashlib


@dataclass
class Notice:
    """单条招聘通知"""
    title: str
    link: str
    date: str
    snippet: str
    source_url: str          # 来源网站
    scraped_at: str          # 抓取时间戳
    content_hash: str = ""   # 用于去重与对比

    def __post_init__(self):
        if not self.content_hash:
            raw = f"{self.title}|{self.link}".strip().lower()
            self.content_hash = hashlib.md5(raw.encode("utf-8", errors="ignore")).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Notice":
        return Notice(**d)


@dataclass
class ScanResult:
    """一次扫描对单个网站的结果"""
    website: str
    all_notices: List[Notice] = field(default_factory=list)
    new_notices: List[Notice] = field(default_factory=list)
    gone_notices: List[Notice] = field(default_factory=list)   # 本次消失的通知
    unchanged_notices: List[Notice] = field(default_factory=list)
    scan_time: str = ""
    error: Optional[str] = None

    @property
    def has_new(self) -> bool:
        return len(self.new_notices) > 0


RECRUIT_KEYWORDS = [
    "招聘", "招募", "招考", "公告", "通知", "岗位", "职位",
    "人才", "简历", "应聘", "录用", "聘用", "选调", "遴选",
    "补招", "急聘", "诚聘", "社招", "校招", "实习",
    "hire", "recruit", "job", "career", "vacancy", "position",
]

DATE_PATTERNS = [
    r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?",
    r"\d{4}\.\d{1,2}\.\d{1,2}",
    r"\d{2}[-/]\d{1,2}[-/]\d{1,2}",
    r"\(\d{4}-\d{2}-\d{2}\)",
]
