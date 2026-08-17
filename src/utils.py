"""
工具函数模块
"""

import sys
from datetime import datetime, timezone, timedelta


# 北京时间时区
TZ_BEIJING = timezone(timedelta(hours=8))


def get_beijing_now() -> datetime:
    """获取当前北京时间"""
    return datetime.now(TZ_BEIJING)


def get_date_info() -> dict:
    """获取当前的日期、星期等信息"""
    now = get_beijing_now()
    weekdays_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return {
        "date": now.strftime("%Y年%m月%d日"),
        "weekday": weekdays_cn[now.weekday()],
        "week_number": now.isocalendar()[1],
        "iso_date": now.strftime("%Y-%m-%d"),
    }


def get_school_week(term_start_date_str: str = None) -> int:
    """计算当前是第几教学周"""
    if not term_start_date_str:
        import os
        term_start_date_str = os.getenv("TERM_START_DATE", "2026-08-25").strip()
    try:
        start = datetime.strptime(term_start_date_str, "%Y-%m-%d").replace(tzinfo=TZ_BEIJING)
        now = get_beijing_now()
        delta = now - start
        if delta.days < 0:
            return 1
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
    print(f"[ℹ] {message}", flush=True)
    sys.stdout.flush()


def log_warning(message: str):
    """打印警告日志"""
    print(f"[⚠] {message}", flush=True)
    sys.stdout.flush()
