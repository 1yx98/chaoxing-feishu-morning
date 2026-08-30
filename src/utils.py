"""
工具函数模块
"""

import sys
import os
from datetime import datetime, timezone, timedelta


# 北京时间时区
TZ_BEIJING = timezone(timedelta(hours=8))


def get_beijing_now() -> datetime:
    """获取当前北京时间（不依赖系统时区设置）"""
    return datetime.now(timezone.utc) + timedelta(hours=8)


def get_date_info(test_date: str = None) -> dict:
    """获取当前的日期、星期等信息"""
    if test_date:
        try:
            if " " in test_date:
                now = datetime.strptime(test_date, "%Y-%m-%d %H:%M").replace(tzinfo=TZ_BEIJING)
            else:
                now = datetime.strptime(test_date, "%Y-%m-%d").replace(tzinfo=TZ_BEIJING)
        except Exception:
            now = get_beijing_now()
    else:
        now = get_beijing_now()

    weekdays_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return {
        "date": now.strftime("%Y年%m月%d日"),
        "weekday": weekdays_cn[now.weekday()],
        "week_number": now.isocalendar()[1],
        "iso_date": now.strftime("%Y-%m-%d"),
    }


def get_school_week(term_start_date_str: str = None, ref_date: datetime = None) -> int:
    """
    计算当前是第几教学周。
    返回 0 表示尚未开学（早于开学日期）。
    """
    if not term_start_date_str:
        term_start_date_str = os.getenv("TERM_START_DATE", "2026-08-31").strip()
    try:
        start = datetime.strptime(term_start_date_str, "%Y-%m-%d").replace(tzinfo=TZ_BEIJING)
        now = ref_date or get_beijing_now()
        delta = now - start
        if delta.days < 0:
            return 0
        return delta.days // 7 + 1
    except Exception:
        return 1


def log_step(message: str, success: bool = True):
    """打印带状态的日志"""
    icon = "✅" if success else "❌"
    print(f"[{icon}] {message}", flush=True)
    sys.stdout.flush()


def log_info(message: str):
    """打印信息日志"""
    print(f"[i] {message}", flush=True)
    sys.stdout.flush()


def log_warning(message: str):
    """打印警告日志"""
    print(f"[⚠] {message}", flush=True)
    sys.stdout.flush()