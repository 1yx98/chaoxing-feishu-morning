"""
主入口模块
每天早晨由 GitHub Actions 自动调用，或手动执行测试。
设置 TEST_DATE 环境变量可模拟指定日期，格式: 2026-05-15 或 2026-05-15 08:05
"""

import os
import sys
import traceback
from datetime import datetime

from utils import get_date_info, get_school_week, log_step, log_info, log_warning, TZ_BEIJING
from chaoxing import get_day_courses
from weather import get_weather
from feishu import send_full_card, send_error_card


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


def generate_reminders(courses: list, weather: dict) -> list:
    """根据课程和天气自动生成今日提醒"""
    reminders = []

    try:
        current_temp = weather.get("current_temp")
        if current_temp is not None:
            try:
                temp = float(current_temp)
                if temp >= 35:
                    reminders.append("☀️ 今天温度很高，注意防晒和补水。")
                elif temp >= 30:
                    reminders.append("☀️ 今天温度较高，注意防晒和补水。")
                elif temp <= 5:
                    reminders.append("❄️ 今天温度较低，注意保暖。")
                elif temp <= 10:
                    reminders.append("🧥 今天有点冷，出门记得加件外套。")
            except (ValueError, TypeError):
                pass

        has_rain_reminder = False
        rain_prob = weather.get("rain_probability", "")
        if rain_prob:
            try:
                import re
                num = re.findall(r'\d+', str(rain_prob))
                if num and int(num[0]) >= 50:
                    reminders.append("🌧 今天有降雨概率，出门记得带伞。")
                    has_rain_reminder = True
            except:
                pass

        weather_desc = str(weather.get("weather_desc", "")).lower()
        if any(w in weather_desc for w in ["雨", "rain"]):
            if not has_rain_reminder:
                reminders.append("🌧 今天有雨，出门记得带伞。")
        if any(w in weather_desc for w in ["雪", "snow"]):
            reminders.append("❄️ 今天有雪，注意保暖和出行安全。")
        if any(w in weather_desc for w in ["霾", "雾"]):
            reminders.append("😷 今天空气质量不佳，建议佩戴口罩。")

        if courses:
            first_course = courses[0]
            if first_course.get("time"):
                reminders.append(f"📖 今天第一节课 {first_course.get('time', '')} 开始，不要迟到哦。")
        else:
            reminders.append("🎉 今天没有课，可以好好休息一下。")

    except Exception as e:
        log_warning(f"生成提醒时出错: {e}")

    return reminders


def main():
    print("=" * 50)
    print("🚀 早安助手开始执行")
    print("=" * 50)

    test_dt = get_test_date()
    if test_dt:
        log_info(f"⚠ 测试模式：模拟日期 {test_dt.strftime('%Y-%m-%d')}")

    # 日期信息
    log_step("获取日期", True)
    test_date_str = test_dt.strftime("%Y-%m-%d") if test_dt else None
    date_info = get_date_info(test_date_str)
    week_num = get_school_week(ref_date=test_dt)
    date_info["week_number"] = week_num
    log_info(f"今天: {date_info['date']} {date_info['weekday']} 第{week_num}周")

    errors = {}

    # 获取课程
    log_step("获取课程", True)
    courses = []
    try:
        courses = get_day_courses(ref_date=test_dt)
        if not courses:
            log_info("今日无课程安排")
        else:
            for i, c in enumerate(courses, 1):
                log_info(f"  课程{i}: {c.get('name')} | {c.get('time', '')} | {c.get('location', '')} | {c.get('teacher', '')}")
    except Exception as e:
        log_step(f"课程获取失败: {e}", False)
        errors["course_failed"] = True

    # 获取天气
    log_step("获取天气", True)
    weather = {}
    try:
        weather = get_weather()
        if weather.get("all_failed"):
            errors["weather_failed"] = True
    except Exception as e:
        log_step(f"天气获取失败: {e}", False)
        errors["weather_failed"] = True
        weather = {"all_failed": True}

    # 生成提醒
    log_step("生成今日提醒", True)
    reminders = generate_reminders(courses, weather)
    for r in reminders:
        log_info(f"  提醒: {r}")

    # 发送飞书卡片
    log_step("生成飞书卡片", True)
    card_data = {
        "date_info": date_info,
        "courses": courses,
        "weather": weather,
        "errors": errors,
        "reminders": reminders,
    }

    log_step("发送飞书消息", True)
    try:
        send_full_card(card_data)
    except Exception as e:
        log_step(f"飞书消息发送失败: {e}", False)
        errors["feishu_failed"] = True
        try:
            send_error_card({"date_info": date_info, "errors": errors})
        except Exception as e2:
            log_step(f"异常通知卡片也发送失败: {e2}", False)

    print("=" * 50)
    if errors:
        log_step("任务完成（部分功能异常，请检查日志）", False)
    else:
        log_step("任务完成", True)
    print("=" * 50)

    return errors


if __name__ == "__main__":
    try:
        errors = main()
        sys.exit(1 if errors else 0)
    except Exception as e:
        print(f"\n❌ 程序异常退出: {e}")
        traceback.print_exc()
        sys.exit(1)