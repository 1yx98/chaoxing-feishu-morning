"""
超星学习通模块
登录超星 → 调用课程表 API (getMyLessons) → 解析当日课程。
API 返回小节编号(1-10)，解析时自动转为大节(1-5)。
"""

import base64
import json
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from utils import log_step, log_info, log_warning, get_beijing_now, get_school_week
from config import (
    CHAOXING_AES_KEY, CHAOXING_LOGIN_URL, CHAOXING_PRELOGIN_URL,
    CHAOXING_SCHEDULE_URL,
    CHAOXING_USERNAME, CHAOXING_PASSWORD,
    REQUEST_TIMEOUT, USER_AGENT,
    SUB_SECTION_TIME, SECTION_TO_PERIOD,
)


def _encrypt_aes(message: str, key: str) -> str:
    key_bytes = key.encode("utf-8")
    cipher = AES.new(key_bytes, AES.MODE_CBC, key_bytes)
    padded = pad(message.encode("utf-8"), AES.block_size)
    return base64.b64encode(cipher.encrypt(padded)).decode("utf-8")


def login(username: str = None, password: str = None) -> requests.Session:
    """登录超星学习通"""
    username = username or CHAOXING_USERNAME
    password = password or CHAOXING_PASSWORD
    if not username or not password:
        raise RuntimeError("超星账号或密码未配置")

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9",
    })

    log_info("正在预热超星登录页面...")
    session.get(CHAOXING_PRELOGIN_URL, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    log_step("预热登录页面", True)

    log_info("正在加密登录凭证...")
    login_data = {
        "fid": "-1",
        "uname": _encrypt_aes(username, CHAOXING_AES_KEY),
        "password": _encrypt_aes(password, CHAOXING_AES_KEY),
        "refer": "http%3A%2F%2Fi.chaoxing.com",
        "t": "true",
        "forbidotherlogin": "0",
        "validate": "",
        "doubleFactorLogin": "0",
        "independentId": "0",
    }
    log_step("加密完成", True)

    log_info("正在提交登录请求...")
    resp = session.post(
        CHAOXING_LOGIN_URL, data=login_data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://passport2.chaoxing.com/login",
        },
        timeout=REQUEST_TIMEOUT, allow_redirects=True,
    )
    try:
        result = resp.json() if resp.text.strip() else {}
    except Exception:
        result = {}
    if result.get("status") is False:
        raise RuntimeError(f"超星登录失败: {result.get('msg2', '')}")
    log_step("超星登录成功", True)
    return session


def _extract_lesson_list(data) -> list:
    """从 API 响应中提取 lessonArray（兼容多种返回结构）"""
    if not isinstance(data, dict):
        return []
    # 结构1: data.lessonArray
    inner = data.get("data", {})
    if isinstance(inner, dict):
        ll = inner.get("lessonArray", [])
        if isinstance(ll, list) and len(ll) > 0:
            return ll
    # 结构2: 顶层 lessonArray
    ll = data.get("lessonArray", [])
    if isinstance(ll, list) and len(ll) > 0:
        return ll
    return []


def _fetch_schedule_api(session: requests.Session, week: int = None) -> list:
    """
    调用课程表 API，返回 lessonArray 列表。
    getMyLessons 接口需要携带 week 参数（第几教学周），否则返回数据不准确。
    """
    params = {"week": week} if week else {}

    # 策略1: 带 week 参数请求
    try:
        resp = session.get(
            CHAOXING_SCHEDULE_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={
                "Referer": "https://kb.chaoxing.com/",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/plain, */*",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        lesson_list = _extract_lesson_list(data)
        if lesson_list:
            log_info(f"API 返回 {len(lesson_list)} 条课程记录（第{week}周）")
            log_info(f"第一条记录字段: {list(lesson_list[0].keys())}")
            return lesson_list

        # 策略2: 带 curriculumId
        inner = data.get("data", {}) if isinstance(data, dict) else {}
        cid = (inner.get("curriculum") or {}).get("id") if isinstance(inner.get("curriculum"), dict) else None
        if cid:
            r2 = session.get(
                CHAOXING_SCHEDULE_URL,
                params={"curriculumId": cid, **params},
                timeout=REQUEST_TIMEOUT,
                headers={
                    "Referer": "https://kb.chaoxing.com/",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            d2 = r2.json()
            ll = _extract_lesson_list(d2)
            if ll:
                log_info(f"API(带curriculumId) 返回 {len(ll)} 条记录（第{week}周）")
                log_info(f"第一条记录字段: {list(ll[0].keys())}")
                return ll
    except Exception:
        pass

    return []


def get_schedule(session=None, ref_date=None) -> list:
    """
    获取当日课程安排。
    从超星课程表 API 获取数据，解析小节编号→大节编号。
    未开学（week<=0）时直接返回空，不登录也不请求。
    """
    now = ref_date if ref_date is not None else get_beijing_now()
    today_weekday = now.weekday()  # 0=周一

    # 未开学则直接返回空，避免无谓登录与请求
    week_num = get_school_week(ref_date=now)
    if week_num <= 0:
        log_info("尚未开学，无课程安排")
        return []

    try:
        sess = session or login()
        sess.get("https://kb.chaoxing.com/", timeout=REQUEST_TIMEOUT)

        log_info(f"当前第 {week_num} 教学周，请求 API 时携带 week={week_num}")
        lesson_list = _fetch_schedule_api(sess, week=week_num)

        if not lesson_list:
            log_warning("课程表 API 未返回数据（开学后会自动获取）")
            return []

        # 筛选今日 + 解析
        today = []
        for lesson in lesson_list:
            day = lesson.get("dayOfWeek") or lesson.get("weekDay") or lesson.get("day", 0)
            try:
                day = int(day)
            except (ValueError, TypeError):
                continue
            if day - 1 == today_weekday:
                today.append(lesson)

        if not today:
            log_info("今日无课程安排")
            return []

        result = []
        for lesson in today:
            # ---- 调试：打印原始节次相关字段 ----
            bgn = lesson.get("beginNumber", "N/A")
            end = lesson.get("endNumber", "N/A")
            log_info(f"  [DEBUG] beginNumber={bgn}, endNumber={end}, "
                     f"startSection={lesson.get('startSection','N/A')}, "
                     f"endSection={lesson.get('endSection','N/A')}, "
                     f"sectionStart={lesson.get('sectionStart','N/A')}, "
                     f"sectionEnd={lesson.get('sectionEnd','N/A')}, "
                     f"length={lesson.get('length','N/A')}, "
                     f"courseName={lesson.get('courseName','N/A')}")

            # 小节编号 → 大节编号（兼容多种字段名）
            sub_start = int(
                lesson.get("startSection") or
                lesson.get("sectionStart") or
                lesson.get("beginNumber") or
                lesson.get("beginSection") or
                0
            )
            # endNumber 优先，其次 endSection/sectionEnd，最后尝试 length 推算
            sub_end_raw = (
                lesson.get("endNumber") or
                lesson.get("endSection") or
                lesson.get("sectionEnd") or
                lesson.get("endSectionNum") or
                None
            )
            if sub_end_raw is not None:
                sub_end = int(sub_end_raw)
            else:
                # 如果 API 没有 endNumber，尝试用 length（课时长度）推算
                sub_len = lesson.get("length")
                if sub_len is not None:
                    try:
                        sub_end = sub_start + int(sub_len) - 1
                    except (ValueError, TypeError):
                        sub_end = sub_start
                else:
                    sub_end = sub_start
            period_start = SECTION_TO_PERIOD.get(sub_start, 0)
            period_end = SECTION_TO_PERIOD.get(sub_end, period_start)

            # 节次解析失败时跳过该课程
            if period_start == 0:
                log_warning(f"课程节次解析失败: sub_start={sub_start}, sub_end={sub_end}, 跳过 {lesson.get('name', lesson.get('courseName', ''))}")
                continue

            # 时间
            start_time = SUB_SECTION_TIME.get(sub_start, {}).get("start", "")
            end_time = SUB_SECTION_TIME.get(sub_end, {}).get("end", "")

            # 课程名（尝试多种字段名）
            name = (
                lesson.get("courseName") or
                lesson.get("name") or
                "未知课程"
            )

            # 教师（尝试多种字段名）
            teacher = (
                lesson.get("teacherName") or
                lesson.get("teacher") or
                lesson.get("teacherInfo") or
                ""
            )

            # 地点（尝试多种字段名）
            location = (
                lesson.get("location") or
                lesson.get("classroom") or
                lesson.get("classRoom") or
                lesson.get("room") or
                lesson.get("place") or
                lesson.get("address") or
                lesson.get("area") or
                lesson.get("teachClass") or
                ""
            )

            result.append({
                "name": name,
                "teacher": teacher,
                "location": location,
                "sections": (
                    f"第{period_start}-{period_end}节"
                    if period_start != period_end
                    else f"第{period_start}节"
                ),
                "time": f"{start_time}-{end_time}" if start_time and end_time else "",
                "start_section": period_start,
                "end_section": period_end,
            })

        result.sort(key=lambda x: x["start_section"])
        log_step(f"今日共 {len(result)} 节课", True)
        for i, c in enumerate(result, 1):
            log_info(f"  课程{i}: {c['name']} | {c['time']} | {c['location']} | {c['teacher']}")
        return result

    except Exception as e:
        log_step(f"课程获取失败: {e}", False)
        return []


def get_day_courses(session=None, ref_date=None) -> list:
    return get_schedule(session, ref_date=ref_date)