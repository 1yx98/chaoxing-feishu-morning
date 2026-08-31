"""
课前提醒长驻进程模块
每天由 GitHub Actions 触发 3 次（早/午/晚），每次持续运行最多 6 小时，
内部每 60 秒轮询一次，到时间自动发送提醒，不依赖 GitHub 的高频 cron。
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


def get_upcoming_period(now: datetime) -> tuple:
    """
    检查当前是否在课前 15-5 分钟窗口内。
    返回 (大节编号, 上课时间, 下课时间) 或 (0, "", "")
    """
    for section_num in sorted(COURSE_TIME_TABLE.keys()):
        info = COURSE_TIME_TABLE[section_num]
        start_time = info["start"]
        start_h, start_m = map(int, start_time.split(":"))
        start_dt = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)

        window_start = start_dt - timedelta(minutes=15)
        window_end = start_dt - timedelta(minutes=5)

        if window_start <= now < window_end:
            return (section_num, start_time, info["end"])

    return (0, "", "")


def _get_test_date():
    """获取测试日期（与 main.py 一致）"""
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


def main():
    test_dt = _get_test_date()
    if test_dt:
        log_info(f"⚠ 测试模式：模拟日期 {test_dt.strftime('%Y-%m-%d %H:%M')}")

    now = test_dt if test_dt else get_beijing_now()

    # 周末不运行
    if now.weekday() >= 5:
        names = ["一", "二", "三", "四", "五", "六", "日"]
        log_info(f"今天是周{names[now.weekday()]}，周末不发送课前提醒")
        return

    date_str = now.strftime("%Y年%m月%d日")
    weekday_str = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]
    log_info(f"课前提醒长驻进程启动：{date_str} {weekday_str} {now.strftime('%H:%M')}")

    # 获取今日课程
    try:
        courses = get_schedule(ref_date=now)
    except Exception as e:
        log_step(f"获取课程失败: {e}", False)
        return

    if not courses:
        log_info("今日无课程安排，进程退出")
        return

    log_info(f"今日共 {len(courses)} 门课程:")
    for c in courses:
        period = c.get("start_section", "?")
        end_section = c.get("end_section", period)
        time_info = COURSE_TIME_TABLE.get(period, {})
        end_info = COURSE_TIME_TABLE.get(end_section, {})
        log_info(f"  {c.get('name')} | 第{period}-{end_section}节 | {time_info.get('start','?')}-{end_info.get('end','?')} | {c.get('location','?')}")

    # 计算最晚提醒时间（最后一节课前 5 分钟）
    last_period = max(c.get("start_section", 0) for c in courses)
    last_time = COURSE_TIME_TABLE.get(last_period, {}).get("start", "19:00")
    last_h, last_m = map(int, last_time.split(":"))
    end_time = now.replace(hour=last_h, minute=last_m, second=0, microsecond=0) - timedelta(minutes=5)
    # 最多运行 6 小时（GitHub Actions 限制）
    max_end = now + timedelta(hours=5, minutes=55)
    if end_time > max_end:
        end_time = max_end

    # 测试模式：只做一次检查并退出
    if test_dt:
        log_info(f"测试模式：模拟时间 {test_dt.strftime('%H:%M')}，仅检查一次")
        period, start_time, end_time_str = get_upcoming_period(now)
        if period > 0:
            matched = next((c for c in courses if c.get("start_section") == period), None)
            if matched:
                log_info(f"  → 会触发提醒: {matched.get('name')} | 第{period}节 | {start_time}-{end_time_str}")
            else:
                log_info(f"  → 第{period}节无课程安排")
        else:
            log_info(f"  → 当前不在任何提醒窗口内")
        return

    log_info(f"计划运行至 {end_time.strftime('%H:%M')}，每 60 秒轮询一次")

    # 已发送提醒的节次（防止重复）
    sent_periods = set()

    while True:
        now = get_beijing_now()

        # 超时退出
        if now >= end_time:
            log_info("到达结束时间，进程退出")
            break

        # 周末退出
        if now.weekday() >= 5:
            log_info("进入周末，进程退出")
            break

        # 检查即将开始的课程
        period, start_time, end_time_str = get_upcoming_period(now)
        if period > 0 and period not in sent_periods:
            sent_periods.add(period)

            # 匹配课程
            matched = next((c for c in courses if c.get("start_section") == period), None)
            if not matched:
                log_info(f"第{period}节 无课程安排，不发送提醒")
                time.sleep(60)
                continue

            course_name = matched.get("name", "未知课程")
            teacher = matched.get("teacher", "")
            location = matched.get("location", "")
            end_section = matched.get("end_section", period)

            if end_section and end_section > period:
                end_time_full = COURSE_TIME_TABLE.get(end_section, {}).get("end", "")
                time_desc = f"{start_time} - {end_time_full}"
                section_desc = f"第{period}-{end_section}节"
            else:
                time_desc = f"{start_time} - {end_time_str}"
                section_desc = f"第{period}节"

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
                log_step(f"✓ 课前提醒已发送: {course_name} | {time_desc}", True)
            except Exception as e:
                log_step(f"发送失败: {course_name} | {e}", False)

        time.sleep(60)  # 每分钟检查一次


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 程序异常退出: {e}")
        traceback.print_exc()
        sys.exit(1)
