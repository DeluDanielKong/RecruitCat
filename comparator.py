# comparator.py — 招聘猫 新旧数据对比模块
from typing import List, Tuple
from models import Notice, ScanResult
from datetime import datetime


def compare(
    website: str,
    old_notices: List[Notice],
    new_notices: List[Notice],
    scan_time: str = "",
) -> ScanResult:
    """
    对比新旧通知列表，返回 ScanResult。
    以 content_hash 作为唯一标识。
    """
    if not scan_time:
        scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    old_hashes = {n.content_hash for n in old_notices}
    new_hashes = {n.content_hash for n in new_notices}

    new_list = [n for n in new_notices if n.content_hash not in old_hashes]
    unchanged_list = [n for n in new_notices if n.content_hash in old_hashes]
    gone_list = [n for n in old_notices if n.content_hash not in new_hashes]

    return ScanResult(
        website=website,
        all_notices=new_notices,
        new_notices=new_list,
        gone_notices=gone_list,
        unchanged_notices=unchanged_list,
        scan_time=scan_time,
    )


def summarize_results(results: List[ScanResult]) -> str:
    """生成纯文本摘要报告"""
    lines = []
    lines.append("=" * 60)
    lines.append(f"  招聘猫 扫描报告  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 60)

    total_new = sum(len(r.new_notices) for r in results)
    total_sites = len(results)
    error_sites = [r for r in results if r.error]

    lines.append(f"共扫描网站: {total_sites} 个 | 发现新通知: {total_new} 条 | 出错: {len(error_sites)} 个")
    lines.append("")

    for r in results:
        if r.error:
            lines.append(f"【错误】{r.website}")
            lines.append(f"  原因: {r.error}")
        else:
            flag = "★ 有新通知" if r.has_new else "  无变化"
            lines.append(f"[{flag}] {r.website}  (共 {len(r.all_notices)} 条)")
            for n in r.new_notices:
                date_str = f"  [{n.date}]" if n.date else ""
                lines.append(f"    🆕{date_str} {n.title}")
                lines.append(f"       {n.link}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
