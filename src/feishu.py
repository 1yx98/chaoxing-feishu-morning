"""
飞书卡片消息模块
"""
import json, uuid, requests
from utils import log_step, log_info, log_warning
from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_RECEIVE_ID, FEISHU_RECEIVE_ID_TYPE, FEISHU_API_BASE, REQUEST_TIMEOUT

class FeishuSender:
    def __init__(self, app_id=None, app_secret=None):
        self.app_id = app_id or FEISHU_APP_ID
        self.app_secret = app_secret or FEISHU_APP_SECRET
        self._token = None

    def _get_token(self):
        if not self.app_id or not self.app_secret:
            raise RuntimeError("飞书 App ID / App Secret 未配置")
        url = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret}, headers={"Content-Type": "application/json; charset=utf-8"}, timeout=REQUEST_TIMEOUT)
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取飞书 token 失败: {data.get('msg')}")
        self._token = data["tenant_access_token"]
        log_step("飞书 Token 获取成功", True)
        return self._token

    def send(self, msg_type, content, receive_id=None, receive_id_type=None):
        if not self._token:
            self._get_token()
        rid = receive_id or FEISHU_RECEIVE_ID
        rtype = receive_id_type or FEISHU_RECEIVE_ID_TYPE
        if not rid:
            raise RuntimeError("飞书接收者 ID 未配置")
        url = f"{FEISHU_API_BASE}/im/v1/messages"
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json; charset=utf-8"}
        if msg_type == "interactive":
            body = {"receive_id": rid, "msg_type": "interactive", "content": json.dumps(content, ensure_ascii=False), "uuid": str(uuid.uuid4())}
        elif msg_type == "text":
            body = {"receive_id": rid, "msg_type": "text", "content": json.dumps({"text": content}, ensure_ascii=False)}
        else:
            raise ValueError(f"不支持的消息类型: {msg_type}")
        resp = requests.post(url, params={"receive_id_type": rtype}, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
        data = resp.json()
        if data.get("code") != 0:
            code = data.get("code")
            msg = data.get("msg", "未知错误")
            if code == 99991663:
                log_warning("Token 过期，重试...")
                self._token = None
                self._get_token()
                return self.send(msg_type, content, receive_id, receive_id_type)
            raise RuntimeError(f"飞书消息发送失败: {msg} (code={code})")
        log_step("飞书消息发送成功", True)
        return data


def build_card(card_data):
    di = card_data.get("date_info", {})
    courses = card_data.get("courses", [])
    weather = card_data.get("weather", {})
    errors = card_data.get("errors", {})
    reminders = card_data.get("reminders", [])

    elements = []
    elements.append({"tag": "markdown", "content": f"📅 **{di.get('date', '')}** · {di.get('weekday', '')}"})
    elements.append({"tag": "hr"})

    if errors.get("course_failed"):
        elements.append({"tag": "markdown", "content": "📚 **今日课程**\n\n⚠️ 课程数据获取失败，请检查超星账号状态。"})
    elif not courses:
        elements.append({"tag": "markdown", "content": "📚 **今日课程**\n\n🎉 今日无课，好好休息！"})
    else:
        lines = ["📚 **今日课程**\n"]
        for i, c in enumerate(courses, 1):
            sec = c.get("sections", "")
            tm = c.get("time", "")
            label = f"第{sec}节" if sec else f"第{i}节"
            if tm:
                label += f"（{tm}）"
            lines.append(f"**{label}**")
            lines.append(c.get("name", "未知课程"))
            if c.get("location"):
                lines.append(f"📍 {c['location']}")
            if c.get("teacher"):
                lines.append(f"👨‍🏫 {c['teacher']}")
            lines.append("")
        elements.append({"tag": "markdown", "content": "\n".join(lines)})

    elements.append({"tag": "hr"})

    if errors.get("weather_failed") or weather.get("all_failed"):
        elements.append({"tag": "markdown", "content": "🌤 **今日天气**\n\n⚠️ 天气数据暂时获取失败。"})
    else:
        wl = ["🌤 **今日天气**\n"]
        cur = weather.get("current_temp", "")
        mx = weather.get("max_temp", "")
        mn = weather.get("min_temp", "")
        if cur or mx or mn:
            parts = []
            if cur:
                parts.append(f"当前 {cur}°C")
            if mx and mn:
                parts.append(f"{mn}°C ~ {mx}°C")
            wl.append(f"🌡 {' · '.join(parts)}")
        desc = weather.get("weather_desc", "")
        if desc:
            wl.append(f"☁️ {desc}")
        hum = weather.get("humidity", "")
        if hum:
            wl.append(f"💧 湿度：{hum if '%' in str(hum) else f'{hum}%'}")
        wd = weather.get("wind_direction", "")
        ws = weather.get("wind_speed", "")
        if wd or ws:
            wl.append(f"💨 风力：{wd} {ws}".strip())
        rain = weather.get("rain_probability", "")
        if rain:
            wl.append(f"🌧 降水概率：{rain}")
        if weather.get("sources_failed"):
            wl.append(f"\n⚠️ 部分数据源不可用")
        elements.append({"tag": "markdown", "content": "\n".join(wl)})

    elements.append({"tag": "hr"})

    if reminders:
        rl = ["💡 **今日提醒**\n"] + [f"• {r}" for r in reminders]
        elements.append({"tag": "markdown", "content": "\n".join(rl)})
    else:
        elements.append({"tag": "markdown", "content": "💡 **今日提醒**\n\n祝你今天学习顺利！📖"})

    elements.append({"tag": "hr"})

    if errors:
        parts = []
        if errors.get("course_failed"):
            parts.append("课程获取失败")
        if errors.get("weather_failed"):
            parts.append("天气获取失败")
        if parts:
            elements.append({"tag": "markdown", "content": f"⚠️ 运行异常：{' · '.join(parts)}。请检查 GitHub Actions 日志。"})

    elements.append({"tag": "markdown", "content": f"⏰ 推送时间：{di.get('date', '')} · 由 GitHub Actions 自动发送"})

    return {
        "schema": "2.0",
        "config": {"wide_screen_mode": True, "enable_forward": True},
        "header": {"title": {"tag": "plain_text", "content": "🌅 早安 · 今日校园提醒"}, "template": "indigo"},
        "body": {"direction": "vertical", "padding": "16px 12px", "elements": elements},
    }


def send_error_card(error_info):
    try:
        s = FeishuSender()
        di = error_info.get("date_info", {})
        errs = error_info.get("errors", {})
        items = []
        if errs.get("course_failed"):
            items.append("❌ 课程获取失败")
        else:
            items.append("✅ 课程获取正常")
        if errs.get("weather_failed"):
            items.append("❌ 天气获取失败")
        else:
            items.append("✅ 天气获取正常")
        card = {
            "schema": "2.0", "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": "⚠️ 早安助手运行异常"}, "template": "red"},
            "body": {"direction": "vertical", "padding": "16px 12px",
                     "elements": [
                         {"tag": "markdown", "content": f"📅 {di.get('date', '')} · {di.get('weekday', '')}\n\n" + "\n".join(items) + "\n\n请前往 GitHub Actions 查看详细日志。"},
                         {"tag": "markdown", "content": "部分功能异常，请检查配置后手动重试。"},
                     ]},
        }
        s.send("interactive", card)
        return True
    except Exception as e:
        log_step(f"发送异常通知失败: {e}", False)
        return False


def send_full_card(card_data):
    s = FeishuSender()
    card = build_card(card_data)
    s.send("interactive", card)
    return True
