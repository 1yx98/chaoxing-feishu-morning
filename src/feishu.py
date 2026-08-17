"""
飞书卡片消息模块
使用 App ID + App Secret 获取 tenant_access_token，
然后通过飞书 Open API 发送交互式卡片消息。
"""

import json
import uuid
import requests

from utils import log_step, log_info, log_warning
from config import (
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_RECEIVE_ID,
    FEISHU_RECEIVE_ID_TYPE,
    FEISHU_API_BASE,
    REQUEST_TIMEOUT,
)


class FeishuSender:
    """飞书消息发送器"""

    def __init__(self, app_id: str = None, app_secret: str = None):
        self.app_id = app_id or FEISHU_APP_ID
        self.app_secret = app_secret or FEISHU_APP_SECRET
        self._token = None

    def _get_token(self) -> str:
        """获取 tenant_access_token"""
        if not self.app_id or not self.app_secret:
            raise RuntimeError(
                "飞书 App ID 或 App Secret 未配置。\n"
                "请在 GitHub Secrets 中设置:\n"
                "  FEISHU_APP_ID\n"
                "  FEISHU_APP_SECRET"
            )

        url = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }
        headers = {"Content-Type": "application/json; charset=utf-8"}

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            data = resp.json()
        except Exception as e:
            raise RuntimeError(f"获取飞书 token 网络请求失败: {e}")

        if data.get("code") != 0:
            raise RuntimeError(
                f"获取飞书 token 失败: {data.get('msg', '未知错误')} (code={data.get('code')})"
            )

        self._token = data["tenant_access_token"]
        log_step("飞书 Tenant Access Token 获取成功", True)
        return self._token

    def send_message(self, msg_type: str, content: dict, receive_id: str = None,
                     receive_id_type: str = None) -> dict:
        """
        发送消息到飞书

        :param msg_type: 消息类型 (interactive / text)
        :param content: 消息内容
        :param receive_id: 接收者 ID
        :param receive_id_type: 接收者 ID 类型
        :return: API 响应
        """
        if not self._token:
            self._get_token()

        receive_id = receive_id or FEISHU_RECEIVE_ID
        receive_id_type = receive_id_type or FEISHU_RECEIVE_ID_TYPE

        if not receive_id:
            raise RuntimeError(
                "飞书接收者 ID 未配置。\n"
                "请在 GitHub Secrets 中设置 FEISHU_RECEIVE_ID。"
            )

        url = f"{FEISHU_API_BASE}/im/v1/messages"
        params = {"receive_id_type": receive_id_type}
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        if msg_type == "interactive":
            body = {
                "receive_id": receive_id,
                "msg_type": "interactive",
                "content": json.dumps(content, ensure_ascii=False),
                "uuid": str(uuid.uuid4()),
            }
        elif msg_type == "text":
            body = {
                "receive_id": receive_id,
                "msg_type": "text",
                "content": json.dumps({"text": content}, ensure_ascii=False),
            }
        else:
            raise ValueError(f"不支持的消息类型: {msg_type}")

        try:
            resp = requests.post(url, params=params, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
            data = resp.json()
        except Exception as e:
            raise RuntimeError(f"飞书消息发送网络请求失败: {e}")

        if data.get("code") != 0:
            error_code = data.get("code")
            error_msg = data.get("msg", "未知错误")

            # 常见错误诊断
            if error_code == 230002:
                raise RuntimeError(f"飞书消息发送失败: 机器人不在目标群聊中，请将机器人添加到群聊。")
            elif error_code == 230013:
                raise RuntimeError(f"飞书消息发送失败: 接收者不在机器人可用范围。")
            elif error_code == 230006:
                raise RuntimeError(f"飞书消息发送失败: 未启用机器人能力。请在飞书开放平台开启机器人功能。")
            elif error_code == 230027:
                raise RuntimeError(f"飞书消息发送失败: 缺少必要权限。请在飞书开放平台申请 im:message 权限。")
            elif error_code == 99991663:
                # Token 过期，重试一次
                log_warning("Token 可能过期，重新获取...")
                self._token = None
                self._get_token()
                return self.send_message(msg_type, content, receive_id, receive_id_type)
            else:
                raise RuntimeError(f"飞书消息发送失败: {error_msg} (code={error_code})")

        log_step("飞书消息发送成功", True)
        return data


def build_card(card_data: dict) -> dict:
    """
    构建飞书卡片 JSON 2.0

    卡片结构：
    ┌────────────────────────────────────┐
    │  🌅 早安 · 今日校园提醒              │  <- header
    │  📅 日期 · 星期                     │
    ├────────────────────────────────────┤
    │  📚 今日课程                        │  <- body section 1
    │  (课程列表)                         │
    ├────────────────────────────────────┤
    │  🌤 今日天气                        │  <- body section 2
    │  (天气数据)                         │
    ├────────────────────────────────────┤
    │  💡 今日提醒                        │  <- body section 3
    │  (智能提醒)                         │
    └────────────────────────────────────┘
    """
    date_info = card_data.get("date_info", {})
    courses = card_data.get("courses", [])
    weather = card_data.get("weather", {})
    errors = card_data.get("errors", {})
    reminders = card_data.get("reminders", [])

    # ===== 构建 Header =====
    header = {
        "title": {
            "tag": "plain_text",
            "content": "🌅 早安 · 今日校园提醒",
        },
        "template": "indigo",  # 靛蓝色主题
    }

    # ===== 构建 Body Elements =====
    elements = []

    # --- 日期行 ---
    elements.append({
        "tag": "markdown",
        "content": f"📅 **{date_info.get('date', '')}** · {date_info.get('weekday', '')}",
    })

    elements.append({"tag": "hr"})

    # ===== 课程部分 =====
    if errors.get("course_failed"):
        elements.append({
            "tag": "markdown",
            "content": (
                "📚 **今日课程**\n\n"
                "⚠️ 课程数据获取失败，请检查超星账号状态。"
            ),
        })
    elif not courses:
        elements.append({
            "tag": "markdown",
            "content": (
                "📚 **今日课程**\n\n"
                "🎉 今日无课，好好休息！"
            ),
        })
    else:
        course_lines = ["📚 **今日课程**\n"]
        for i, course in enumerate(courses, 1):
            sections = course.get("sections", "")
            time = course.get("time", "")
            name = course.get("name", "未知课程")
            teacher = course.get("teacher", "")
            location = course.get("location", "")

            section_label = f"第{sections}节" if sections else f"第{i}节"
            if time:
                section_label += f"（{time}）"

            course_lines.append(f"**{section_label}**")
            course_lines.append(f"{name}")
            if location:
                course_lines.append(f"📍 {location}")
            if teacher:
                course_lines.append(f"👨‍🏫 {teacher}")
            course_lines.append("")

        elements.append({
            "tag": "markdown",
            "content": "\n".join(course_lines),
        })

    elements.append({"tag": "hr"})

    # ===== 天气部分 =====
    if errors.get("weather_failed") or weather.get("all_failed"):
        elements.append({
            "tag": "markdown",
            "content": (
                "🌤 **今日天气**\n\n"
                "⚠️ 天气数据暂时获取失败，请稍后重试。"
            ),
        })
    else:
        weather_lines = ["🌤 **今日天气**\n"]

        # 温度
        current = weather.get("current_temp", "")
        max_t = weather.get("max_temp", "")
        min_t = weather.get("min_temp", "")

        if current or max_t or min_t:
            temp_parts = []
            if current:
                temp_parts.append(f"当前 {current}°C")
            if max_t and min_t:
                temp_parts.append(f"{min_t}°C ~ {max_t}°C")
            elif max_t:
                temp_parts.append(f"最高 {max_t}°C")
            elif min_t:
                temp_parts.append(f"最低 {min_t}°C")
            weather_lines.append(f"🌡 {' · '.join(temp_parts)}")

        # 天气状况
        desc = weather.get("weather_desc", "")
        if desc:
            weather_lines.append(f"☁️ {desc}")

        # 湿度
        humidity = weather.get("humidity", "")
        if humidity:
            # 中国天气网返回 "81%"，wttr返回 "81"
            humidity_str = humidity if "%" in str(humidity) else f"{humidity}%"
            weather_lines.append(f"💧 湿度：{humidity_str}")

        # 风力
        wind = ""
        if weather.get("wind_direction") and weather.get("wind_speed"):
            wind = f"{weather['wind_direction']} {weather['wind_speed']}"
        elif weather.get("wind_speed"):
            wind = str(weather["wind_speed"])
        if wind:
            weather_lines.append(f"💨 风力：{wind}")

        # 降水概率
        rain = weather.get("rain_probability", "")
        if rain:
            weather_lines.append(f"🌧 降水概率：{rain}")

        # 空气质量
        air = weather.get("air_quality", "")
        if air:
            weather_lines.append(f"🍃 空气质量：{air}")

        # 数据源说明
        if weather.get("sources_failed"):
            weather_lines.append(f"\n⚠️ 部分数据源不可用，当前数据来自：{weather.get('source', '')}")

        elements.append({
            "tag": "markdown",
            "content": "\n".join(weather_lines),
        })

    elements.append({"tag": "hr"})

    # ===== 提醒部分 =====
    if reminders:
        reminder_lines = ["💡 **今日提醒**\n"]
        for r in reminders:
            reminder_lines.append(f"• {r}")
        elements.append({
            "tag": "markdown",
            "content": "\n".join(reminder_lines),
        })
    else:
        elements.append({
            "tag": "markdown",
            "content": "💡 **今日提醒**\n\n祝你今天学习顺利！📖",
        })

    elements.append({"tag": "hr"})

    # ===== 底部 =====
    if errors:
        error_parts = []
        if errors.get("course_failed"):
            error_parts.append("课程获取失败")
        if errors.get("weather_failed"):
            error_parts.append("天气获取失败")
        if error_parts:
            elements.append({
                "tag": "markdown",
                "content": f"⚠️ 运行异常：{' · '.join(error_parts)}。请检查 GitHub Actions 日志。",
            })

    # 底部时间戳
    elements.append({
        "tag": "markdown",
        "content": f"⏰ 推送时间：{date_info.get('date', '')} · 由 GitHub Actions 自动发送",
    })

    card = {
        "schema": "2.0",
        "config": {
            "wide_screen_mode": True,
            "enable_forward": True,
        },
        "header": header,
        "body": {
            "direction": "vertical",
            "padding": "16px 12px",
            "elements": elements,
        },
    }

    return card


def send_error_card(error_info: dict) -> bool:
    """
    发送错误通知卡片（当主流程部分失败时）

    :param error_info: 包含 errors 字段的字典
    :return: 是否发送成功
    """
    try:
        sender = FeishuSender()

        date_info = error_info.get("date_info", {})
        errors = error_info.get("errors", {})

        error_items = []
        if errors.get("course_failed"):
            error_items.append("❌ 课程获取失败")
        else:
            error_items.append("✅ 课程获取正常")
        if errors.get("weather_failed"):
            error_items.append("❌ 天气获取失败")
        else:
            error_items.append("✅ 天气获取正常")

        card = {
            "schema": "2.0",
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "⚠️ 早安助手运行异常"},
                "template": "red",
            },
            "body": {
                "direction": "vertical",
                "padding": "16px 12px",
                "elements": [
                    {
                        "tag": "markdown",
                        "content": (
                            f"📅 {date_info.get('date', '')} · {date_info.get('weekday', '')}\n\n"
                            + "\n".join(error_items)
                            + "\n\n请前往 GitHub Actions 查看详细日志。"
                        ),
                    },
                    {
                        "tag": "markdown",
                        "content": "部分功能异常，请检查配置后手动重试。",
                    },
                ],
            },
        }

        sender.send_message("interactive", card)
        log_step("异常通知卡片已发送", True)
        return True
    except Exception as e:
        log_step(f"发送异常通知卡片失败: {e}", False)
        return False


def send_full_card(card_data: dict) -> bool:
    """
    发送完整的早安卡片

    :param card_data: 卡片数据字典
    :return: 是否发送成功
    """
    try:
        sender = FeishuSender()
        card = build_card(card_data)
        sender.send_message("interactive", card)
        log_step("早安卡片发送成功", True)
        return True
    except Exception as e:
        log_step(f"早安卡片发送失败: {e}", False)
        raise
