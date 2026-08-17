#!/usr/bin/env python3
"""超星课表 + 西安石油大学鄠邑校区天气 → 飞书早安推送"""
import sys, traceback
from utils import get_date_info, get_school_week, log_step, log_info, log_warning
from chaoxing import login, get_day_courses
from weather import get_weather
from feishu import send_full_card, send_error_card


def generate_reminders(courses, weather):
    reminders = []
    try:
        current_temp = weather.get("current_temp")
        if current_temp is not None:
            try:
                temp = float(current_temp)
                if temp >= 35:
                    reminders.append("☀️ 今天温度很高，注意防晒和补水，尽量避免长时间户外活动。")
                elif temp >= 30:
                    reminders.append("☀️ 今天温度较高，注意防晒和补水。")
                elif temp <= 5:
                    reminders.append("❄️ 今天温度较低，记得穿暖和点，注意保暖。")
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
            reminders.append("🎉 今天没有课，可以复习功课或好好休息一下。")
    except Exception as e:
        log_warning(f"生成提醒时出错: {e}")
    return reminders


def main():
    print("=" * 50)
    print("🚀 早安助手开始执行")
    print("=" * 50)
    log_step("获取日期", True)
    date_info = get_date_info()
    week_num = get_school_week()
    date_info["week_number"] = week_num
    log_info(f"今天: {date_info['date']} {date_info['weekday']} 第{week_num}周")
    errors = {}
    log_step("获取课程", True)
    courses = []
    try:
        session = login()
        courses = get_day_courses(session, week_num)
        if not courses:
            log_info("今日无课程安排")
        else:
            for i, c in enumerate(courses, 1):
                log_info(f"  课程{i}: {c.get('name')} {c.get('sections', '')} {c.get('time', '')}")
    except Exception as e:
        log_step(f"课程获取失败: {e}", False)
        errors["course_failed"] = True
        log_info("课程部分将显示为获取失败，不影响天气信息的发送")
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
    log_step("生成今日提醒", True)
    reminders = generate_reminders(courses, weather)
    for r in reminders:
        log_info(f"  提醒: {r}")
    log_step("生成飞书卡片", True)
    card_data = {"date_info": date_info, "courses": courses, "weather": weather, "errors": errors, "reminders": reminders}
    log_step("发送飞书消息", True)
    try:
        send_full_card(card_data)
    except Exception as e:
        log_step(f"飞书消息发送失败: {e}", False)
        try:
            send_error_card({"date_info": date_info, "errors": {"course_failed": True, "weather_failed": True}})
        except:
            pass
        raise
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
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 程序异常退出: {e}")
        traceback.print_exc()
        sys.exit(1)
