"""
单次课前提醒脚本
由 GitHub Actions 在每节课前 30 分钟触发，脚本自动识别接下来要上的课，
等待到课前 15 分钟准时发送提醒。
每个提醒独立运行，比长驻进程更可靠。
"""

import os
import sys
import time
import traceback
from datetime import datetime, timedelta

from utils import log_step, log_info, log_warning, get_beijing_now, TZ_BEIJING
from config import COURSE_TIME_TABLE
from chaoxing import get_schedule
from feishu import send_class_notification


def get_test_date():
    """获取测试日期"""
    test_date = os.getenv("TEST_DATE", "").strip()
    if test_date:
        try:
            if " " in test_date:
                return datetime.strptime(test_date, "%Y-%m-%d %H:%M").replace(tzinfo=TZ_BEIJING)
            else:
                return datetime.strptime(test_date, "%Y-%m-%d").replace(tzinfo=TZ_BEIJING)
        except Exception:
            pass
    return None


def fetch_schedule_with_retry(ref_date, max_retries=3, delay=20):
    """获取课程表，失败重试"""
    for attempt in range(1, max_retries + 1):
        try:
            return get_schedule(ref_date=ref_date)
        except Exception as e:
            log_warning(f"获取课程表失败（第{attempt}/{max_retries}次）: {e}")
            if attempt < max_retries:
                time.sleep(delay)
    return None


def find_upcoming_courses(now, courses, window_minutes=30):
    """找到未来 window_minutes 分钟内要上的课"""
    upcoming = []
    for period in sorted(COURSE_TIME_TABLE.keys()):
        info = COURSE_TIME_TABLE[period]
        start_h, start_m = map(int, info["start"].split(":"))
        class_start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        if now < class_start <= now + timedelta(minutes=window_minutes):
            matched = next((c for c in courses if c.get("start_section") == period), None)
            if matched:
                upcoming.append((period, class_start, matched))
    return upcoming


def main():
    test_dt = get_test_date()
    now = test_dt if test_dt else get_beijing_now()

    log_info(f"课前提醒启动：{now.strftime('%Y-%m-%d %H:%M:%S')}")

    # 周末不运行
    if now.weekday() >= 5:
        names = ["一", "二", "三", "四", "五", "六", "日"]
        log_info(f"今天是周{names[now.weekday()]}，周末不发送提醒")
        return

    # 获取课程表（重试3次）
    courses = fetch_schedule_with_retry(now)
    if courses is None:
        log_step("获取课程表多次失败，退出", False)
        sys.exit(1)

    if not courses:
        log_info("今日无课程安排，退出")
        return

    # 找到未来30分钟内要上的课
    upcoming = find_upcoming_courses(now, courses, window_minutes=30)

    if not upcoming:
        log_info("未来30分钟内无课程，退出")
        return

    for period, class_start, matched in upcoming:
        remind_time = class_start - timedelta(minutes=15)
        start_time_str = class_start.strftime("%H:%M")

        # 已经上课了，跳过
        if now >= class_start:
            log_info(f"第{period}节已上课，跳过")
            continue

        # 还没到提醒时间，等待
        if now < remind_time:
            wait_seconds = int((remind_time - now).total_seconds())
            log_info(f"第{period}节 {start_time_str} 上课，等待 {wait_seconds // 60} 分 {wait_seconds % 60} 秒到 {remind_time.strftime('%H:%M')} 发送")
            time.sleep(wait_seconds)

        # 等待结束后重新获取时间
        now = get_beijing_now()
        if now >= class_start:
            log_info(f"等待后第{period}节已上课，跳过")
            continue

        # 组装课程信息
        course_name = matched.get("name", "未知课程")
        teacher = matched.get("teacher", "")
        location = matched.get("location", "")
        end_section = matched.get("end_section", period)

        if end_section and end_section > period:
            end_time_full = COURSE_TIME_TABLE.get(end_section, {}).get("end", "")
            time_desc = f"{start_time_str} - {end_time_full}"
            section_desc = f"第{period}-{end_section}节"
        else:
            time_desc = f"{start_time_str} - {COURSE_TIME_TABLE[period]['end']}"
            section_desc = f"第{period}节"

        # 发送提醒
        try:
            send_class_notification(
                course_name=course_name,
                time_desc=time_desc,
                section_desc=section_desc,
                teacher=teacher,
                location=location,
                date_str=now.strftime("%Y年%m月%d日"),
                weekday_str=["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()],
            )
            log_step(f"✓ 已发送: {course_name} | {time_desc} | {location}", True)
        except Exception as e:
            log_step(f"发送失败: {course_name} | {e}", False)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 程序异常退出: {e}")
        traceback.print_exc()
        sys.exit(1)
