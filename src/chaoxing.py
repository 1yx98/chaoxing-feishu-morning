"""
超星学习通模块
负责登录超星学习通并获取课程表/课程列表
"""

import base64
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from utils import log_step, log_info, log_warning
from config import (
    CHAOXING_AES_KEY, CHAOXING_LOGIN_URL, CHAOXING_PRELOGIN_URL,
    CHAOXING_COURSE_URL, CHAOXING_SCHEDULE_URL,
    CHAOXING_USERNAME, CHAOXING_PASSWORD,
    REQUEST_TIMEOUT, USER_AGENT, COURSE_TIME_TABLE,
)


def _encrypt_aes(message: str, key: str) -> str:
    """超星 fanyalogin 接口 AES-CBC 加密"""
    key_bytes = key.encode("utf-8")
    iv_bytes = key_bytes
    message_bytes = message.encode("utf-8")
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
    padded = pad(message_bytes, AES.block_size)
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(encrypted).decode("utf-8")


def login(username: str = None, password: str = None) -> requests.Session:
    """登录超星学习通，返回带 Cookie 的 Session"""
    username = username or CHAOXING_USERNAME
    password = password or CHAOXING_PASSWORD

    if not username or not password:
        raise RuntimeError("超星账号或密码未配置。请在 GitHub Secrets 中设置 CHAOXING_USERNAME 和 CHAOXING_PASSWORD。")

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })

    log_info("正在预热超星登录页面...")

    try:
        pre_resp = session.get(CHAOXING_PRELOGIN_URL, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        pre_resp.raise_for_status()
        log_step("预热登录页面", True)
    except Exception as e:
        log_step(f"预热登录页面失败: {e}", False)
        raise RuntimeError(f"无法访问超星登录页面: {e}")

    log_info("正在加密登录凭证...")
    encrypted_uname = _encrypt_aes(username, CHAOXING_AES_KEY)
    encrypted_password = _encrypt_aes(password, CHAOXING_AES_KEY)
    log_step("加密完成", True)

    log_info("正在提交登录请求...")
    login_data = {
        "fid": "-1", "uname": encrypted_uname, "password": encrypted_password,
        "refer": "http%3A%2F%2Fi.chaoxing.com", "t": "true",
        "forbidotherlogin": "0", "validate": "",
        "doubleFactorLogin": "0", "independentId": "0",
    }

    try:
        login_resp = session.post(
            CHAOXING_LOGIN_URL, data=login_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://passport2.chaoxing.com/login",
            },
            timeout=REQUEST_TIMEOUT, allow_redirects=True,
        )
        login_resp.raise_for_status()
    except Exception as e:
        log_step(f"登录请求失败: {e}", False)
        raise RuntimeError(f"超星登录网络请求失败: {e}")

    login_result = login_resp.json() if login_resp.text else {}
    if login_result.get("status") is False:
        error_msg = login_result.get("msg2", login_result.get("msg", "未知错误"))
        log_step(f"超星登录失败: {error_msg}", False)
        if "验证码" in str(error_msg) or "validate" in str(error_msg).lower():
            raise RuntimeError("超星登录需要验证码，当前版本暂不支持。请等待一段时间后再试。")
        elif "账号或密码" in str(error_msg) or "不存在" in str(error_msg):
            raise RuntimeError("超星登录失败：账号或密码错误。请检查 GitHub Secrets。")
        else:
            raise RuntimeError(f"超星登录失败: {error_msg}")

    cookies = session.cookies.get_dict()
    if "_uid" not in cookies:
        log_step("超星登录未返回有效 Cookie", False)
        raise RuntimeError("超星登录后未获取到有效 Cookie。")

    log_step(f"超星登录成功", True)
    return session


def get_courses(session: requests.Session) -> list:
    """获取当前学期的课程列表"""
    log_info("正在获取课程列表...")
    try:
        resp = session.get(CHAOXING_COURSE_URL, timeout=REQUEST_TIMEOUT, headers={"Referer": "https://i.chaoxing.com/"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log_step(f"获取课程列表失败: {e}", False)
        return []

    if not isinstance(data, dict):
        return []

    channel_list = data.get("channelList", [])
    if not channel_list:
        log_info("未找到课程数据")
        return []

    courses = []
    for item in channel_list:
        content = item.get("content", {}) or {}
        course_info = content.get("course", {}) or {}
        courses.append({
            "course_name": course_info.get("name", "未知课程"),
            "teacher_name": course_info.get("teacherfactor", "未知教师"),
            "course_id": course_info.get("id", ""),
            "class_id": content.get("id", ""),
            "classroom": item.get("classroom", "") or "",
        })

    log_step(f"获取到 {len(courses)} 门课程", True)
    return courses


def get_schedule(session: requests.Session, week: int = None) -> list:
    """获取指定周的课程表，筛出今天的课程"""
    from utils import get_school_week, get_beijing_now

    if week is None:
        week = get_school_week()

    log_info(f"正在获取第 {week} 周课程表...")

    try:
        resp = session.get(
            f"{CHAOXING_SCHEDULE_URL}?week={week}",
            timeout=REQUEST_TIMEOUT, headers={"Referer": "https://kb.chaoxing.com/"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log_step(f"获取课程表失败: {e}", False)
        return []

    if not isinstance(data, dict):
        return []

    lesson_list = data.get("data", []) if isinstance(data, dict) else data
    if not isinstance(lesson_list, list):
        lesson_list = []

    if not lesson_list:
        log_info("该周暂无课程安排")
        return []

    today_weekday = get_beijing_now().weekday()

    today_lessons = []
    for lesson in lesson_list:
        day = lesson.get("dayOfWeek") or lesson.get("weekDay") or lesson.get("day", 0)
        try:
            day = int(day)
        except (ValueError, TypeError):
            continue
        if day - 1 == today_weekday:
            today_lessons.append(lesson)

    if not today_lessons:
        log_info("今日无课程安排")
        return []

    courses = []
    for lesson in today_lessons:
        start_section = lesson.get("startSection") or lesson.get("sectionStart") or 0
        end_section = lesson.get("endSection") or lesson.get("sectionEnd") or 0
        try:
            start_section = int(start_section)
            end_section = int(end_section)
        except (ValueError, TypeError):
            start_section = 0
            end_section = 0

        start_time = COURSE_TIME_TABLE.get(start_section, {}).get("start", "")
        end_time = COURSE_TIME_TABLE.get(end_section, {}).get("end", "")

        courses.append({
            "name": lesson.get("courseName") or lesson.get("name", "未知课程"),
            "teacher": lesson.get("teacherName") or lesson.get("teacher", ""),
            "location": lesson.get("location") or lesson.get("classroom") or lesson.get("place", ""),
            "sections": f"{start_section}-{end_section}节" if start_section and end_section else "",
            "time": f"{start_time}-{end_time}" if start_time and end_time else "",
            "start_section": start_section,
            "end_section": end_section,
        })

    courses.sort(key=lambda x: x["start_section"])
    log_step(f"今日共 {len(courses)} 节课", True)
    return courses


def get_day_courses(session: requests.Session, week: int = None) -> list:
    """获取今天的课程安排"""
    courses = get_schedule(session, week)
    if not courses:
        log_info("课程表为空，尝试从课程列表获取...")
        all_courses = get_courses(session)
        if all_courses:
            courses = []
            for c in all_courses:
                courses.append({
                    "name": c.get("course_name", "未知课程"),
                    "teacher": c.get("teacher_name", ""),
                    "location": c.get("classroom", ""),
                    "sections": "", "time": "",
                    "start_section": 0, "end_section": 0,
                })
            log_info(f"从课程列表获取到 {len(courses)} 门课程")
    return courses
