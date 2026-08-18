"""
课前提醒模块
每节课前15分钟检查，有课就发送提醒，没课就跳过。
"""

import os
import sys
import traceback
from datetime import datetime, timedelta

from utils import log_step, log_info, log_warning, get_beijing_now, TZ_BEIJING
from config import COURSE_TIME_TABLE
from chaoxing import get_schedule
from feishu import send_class_notification


def get_test_now():
    """获取当前时间（支持 TEST_DATE 模拟）"""
    test_date = os.getenv("TEST_DATE", "").strip()
    if not test_date:
        return get_beijing_now()
    try:
        if " " in test_date:
            return datetime.strptime(test_date, "%Y-%m-%d %H:%M").replace(tzinfo=TZ_BEIJING)
        else:
            now = get_beijing_now()
            return datetime.strptime(test_date, "%Y-%m-%d").replace(
                hour=now.hour, minute=now.minute, second=0, tzinfo=TZ_BEIJING
            )
    except Exception as e:
        log_warning(f"TEST_DATE 解析失败: {e}")
        return get_beijing_now()


def get_upcoming_period(now: datetime) -> tuple:
    """
    检查当前是否在课前15-10分钟窗口内（5分钟窗口，防止 cron 每5分钟重复触发）。
    返回 (大节编号, 上课时间, 下课时间) 或 (0, "", "")
    """
    for section_num in sorted(COURSE_TIME_TABLE.keys()):
        info = COURSE_TIME_TABLE[section_num]
        start_time = info["start"]
        start_h, start_m = map(int, start_time.split(":"))
        start_dt = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)

        # 窗口：课前15分钟 到 课前10分钟（5分钟宽，防止重复）
        window_start = start_dt - timedelta(minutes=15)
        window_end = start_dt - timedelta(minutes=10)

        if window_start <= now < window_end:
            return (section_num, start_time, info["end"])

    return (0, "", "")


def main():
    """主流程：检查即将开始的课程并发送提醒"""
    now = get_test_now()

    # 周末不提醒
    if now.weekday() >= 5:
        names = ["一", "二", "三", "四", "五", "六", "日"]
        log_info(f"今天是周{names[now.weekday()]}，周末不发送课前提醒")
        return

    date_str = now.strftime("%Y年%m月%d日")
    weekday_str = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]
    log_info(f"当前时间：{date_str} {weekday_str} {now.strftime('%H:%M')}")

    if os.getenv("TEST_DATE"):
        log_info(f"⚠ 测试模式：模拟 {os.getenv('TEST_DATE')}")

    # 检查即将开始的课程
    period, start_time, end_time = get_upcoming_period(now)
    if period == 0:
        log_info("当前没有 15 分钟内即将开始的课程，跳过")
        return

    period_name = COURSE_TIME_TABLE.get(period, {}).get("name", f"第{period}节")
    log_info(f"检测到 {period_name}（{start_time}-{end_time}）将在 15 分钟内开始，检查课程...")

    # 获取今日课程
    try:
        courses = get_schedule(ref_date=now)
    except Exception as e:
        log_step(f"获取课程失败: {e}", False)
        return

    if not courses:
        log_info("今日无课程安排，不发送提醒")
        return

    # 匹配：start_section == period
    matched = next((c for c in courses if c.get("start_section") == period), None)
    if not matched:
        log_info(f"{period_name} 无课程安排，不发送提醒")
        return

    # 发送提醒
    try:
        course_name = matched.get("name", "未知课程")
        teacher = matched.get("teacher", "")
        location = matched.get("location", "")
        end_section = matched.get("end_section", period)

        if end_section and end_section > period:
            end_time_full = COURSE_TIME_TABLE.get(end_section, {}).get("end", "")
            time_desc = f"{start_time} - {end_time_full}"
            section_desc = f"第{period}-{end_section}节"
        else:
            time_desc = f"{start_time} - {end_time}"
            section_desc = f"第{period}节"

        send_class_notification(
            course_name=course_name,
            time_desc=time_desc,
            section_desc=section_desc,
            teacher=teacher,
            location=location,
            date_str=date_str,
            weekday_str=weekday_str,
        )
        log_step(f"课前提醒已发送：{course_name} | {time_desc} | {location} | {teacher}", True)
    except Exception as e:
        log_step(f"发送课前提醒失败: {e}", False)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 程序异常退出: {e}")
        traceback.print_exc()
        sys.exit(1)