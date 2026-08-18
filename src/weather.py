"""
天气模块 - 多数据源容错
1. Open-Meteo（免费，无需 Key）
2. wttr.in（免费，无需 Key）
3. 墨迹天气（免费，网页解析）
4. 和风天气（可选，需 Key）
"""

import json
import re
import requests
from typing import Optional, Dict, Any

from utils import log_step, log_info, log_warning
from config import (
    WEATHER_CITY_ID, WEATHER_CITY_NAME, QWEATHER_API_KEY,
    MOJI_WEATHER_URL, REQUEST_TIMEOUT, USER_AGENT,
)

HUYI_LAT = 34.16
HUYI_LON = 108.61

WMO_CODES = {
    0: "晴天", 1: "大部晴朗", 2: "多云", 3: "阴天",
    45: "有雾", 48: "雾凇",
    51: "小毛毛雨", 53: "中毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    80: "小阵雨", 81: "中阵雨", 82: "大阵雨",
    95: "雷暴", 96: "小冰雹雷暴", 99: "大冰雹雷暴",
}

EMPTY = {
    "city": WEATHER_CITY_NAME, "current_temp": None, "max_temp": None,
    "min_temp": None, "weather_desc": None, "wind_direction": None,
    "wind_speed": None, "humidity": None, "rain_probability": None,
    "air_quality": None, "source": None,
    "sources_available": [], "sources_failed": [],
}


def _get(url, referer=None):
    h = {"User-Agent": USER_AGENT, "Accept": "application/json, text/html, */*", "Accept-Language": "zh-CN,zh;q=0.9"}
    if referer:
        h["Referer"] = referer
    return requests.get(url, headers=h, timeout=REQUEST_TIMEOUT)


def _wind_dir(deg):
    if deg is None:
        return ""
    dirs = ["北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风"]
    return dirs[int((deg + 22.5) % 360 / 45)]


def fetch_openmeteo():
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={HUYI_LAT}&longitude={HUYI_LON}"
           f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m"
           f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
           f"&timezone=Asia/Shanghai&forecast_days=1")
    log_info("正在从 Open-Meteo 获取天气...")
    try:
        data = _get(url).json()
        cur = data.get("current", {})
        daily = data.get("daily", {})
        if not cur:
            return None
        code = cur.get("weather_code")
        wd = _wind_dir(cur.get("wind_direction_10m"))
        ws = cur.get("wind_speed_10m")
        r = {
            "city": WEATHER_CITY_NAME,
            "current_temp": cur.get("temperature_2m"),
            "humidity": cur.get("relative_humidity_2m"),
            "wind_direction": wd,
            "wind_speed": f"{ws}km/h" if ws else None,
            "weather_desc": WMO_CODES.get(code, f"未知"),
            "max_temp": (daily.get("temperature_2m_max") or [None])[0],
            "min_temp": (daily.get("temperature_2m_min") or [None])[0],
            "rain_probability": (daily.get("precipitation_probability_max") or [None])[0],
            "air_quality": None, "source": "Open-Meteo",
        }
        log_step("Open-Meteo 获取成功", True)
        return r
    except Exception as e:
        log_warning(f"Open-Meteo 失败: {e}")
        return None


def fetch_wttr():
    url = f"https://wttr.in/{HUYI_LAT},{HUYI_LON}?format=j1&lang=zh"
    log_info("正在从 wttr.in 获取天气...")
    try:
        data = _get(url).json()
        cur = data.get("current_condition", [{}])[0]
        days = data.get("weather", [])
        if not cur:
            return None
        r = {
            "city": WEATHER_CITY_NAME,
            "current_temp": cur.get("temp_C"),
            "humidity": cur.get("humidity"),
            "wind_speed": cur.get("windspeedKmph"),
            "wind_direction": cur.get("winddir16Point"),
            "weather_desc": (cur.get("weatherDesc", [{}])[0].get("value") if cur.get("weatherDesc") else None),
            "max_temp": days[0].get("maxtempC") if days else None,
            "min_temp": days[0].get("mintempC") if days else None,
            "rain_probability": (days[0].get("hourly", [{}])[0].get("chanceofrain") if days and days[0].get("hourly") else None),
            "air_quality": None, "source": "wttr.in",
        }
        log_step("wttr.in 获取成功", True)
        return r
    except Exception as e:
        log_warning(f"wttr.in 失败: {e}")
        return None


def fetch_moji():
    """
    从墨迹天气网页 meta description 中解析实况天气。
    免费、无需 Key，但仅提供当日实况 + 白天/夜间预报。
    格式示例：
      鄠邑区今天实况：21度 阵雨，湿度：98%，西南风：3级。
      白天：28度,小雨。 夜间：小雨，21度，...
    """
    log_info("正在从墨迹天气获取...")
    try:
        h = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        resp = requests.get(MOJI_WEATHER_URL, headers=h, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        html = resp.text

        # 提取 meta description
        match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
        if not match:
            log_warning("墨迹天气: 未找到 meta description")
            return None

        desc = match.group(1)
        log_info(f"墨迹天气 meta: {desc[:80]}...")

        result = {
            "city": WEATHER_CITY_NAME,
            "current_temp": None, "max_temp": None, "min_temp": None,
            "weather_desc": None, "wind_direction": None, "wind_speed": None,
            "humidity": None, "rain_probability": None, "air_quality": None,
            "source": "墨迹天气",
        }

        # 实况: "21度 阵雨，湿度：98%，西南风：3级"
        cond_match = re.search(r'实况[：:]\s*(\d+)\s*度\s*(\S+?)[，,]', desc)
        if cond_match:
            result["current_temp"] = int(cond_match.group(1))
            result["weather_desc"] = cond_match.group(2)

        # 湿度
        hum_match = re.search(r'湿度[：:]\s*(\d+)%', desc)
        if hum_match:
            result["humidity"] = int(hum_match.group(1))

        # 风向风力
        wind_match = re.search(r'([东西南北]+风)[：:]\s*(\d+)\s*级', desc)
        if wind_match:
            result["wind_direction"] = wind_match.group(1)
            result["wind_speed"] = wind_match.group(2) + "级"

        # 白天最高温: "白天：28度,小雨"
        day_match = re.search(r'白天[：:]\s*(\d+)\s*度[，,]\s*(\S+)', desc)
        if day_match:
            result["max_temp"] = int(day_match.group(1))

        # 夜间最低温: "夜间：小雨，21度"
        night_match = re.search(r'夜间[：:]\s*\S+[，,]\s*(\d+)\s*度', desc)
        if night_match:
            result["min_temp"] = int(night_match.group(1))

        if result["current_temp"] is None:
            log_warning("墨迹天气: 解析失败，未提取到有效数据")
            return None

        log_step("墨迹天气获取成功", True)
        return result

    except Exception as e:
        log_warning(f"墨迹天气失败: {e}")
        return None


def fetch_qweather():
    if not QWEATHER_API_KEY:
        return None
    log_info("正在从和风天气获取...")
    r = {"city": WEATHER_CITY_NAME, "current_temp": None, "max_temp": None, "min_temp": None,
         "weather_desc": None, "wind_direction": None, "wind_speed": None,
         "humidity": None, "rain_probability": None, "air_quality": None, "source": "和风天气"}
    try:
        now = _get(f"https://devapi.qweather.com/v7/weather/now?location={WEATHER_CITY_ID}&key={QWEATHER_API_KEY}")
        now = now.json() if now else {}
        if now.get("code") == "200":
            n = now.get("now", {})
            r["current_temp"] = n.get("temp")
            r["weather_desc"] = n.get("text")
            r["wind_direction"] = n.get("windDir")
            r["wind_speed"] = n.get("windScale") + "级" if n.get("windScale") else None
            r["humidity"] = n.get("humidity")
    except Exception as e:
        log_warning(f"和风实时失败: {e}")
        return None
    try:
        fc = _get(f"https://devapi.qweather.com/v7/weather/3d?location={WEATHER_CITY_ID}&key={QWEATHER_API_KEY}")
        fc = fc.json() if fc else {}
        if fc.get("code") == "200":
            d = fc.get("daily", [])
            if d:
                r["max_temp"] = d[0].get("tempMax")
                r["min_temp"] = d[0].get("tempMin")
    except Exception as e:
        log_warning(f"和风预报失败: {e}")
    log_step("和风天气获取成功", True)
    return r


def _merge(*results):
    m = EMPTY.copy()
    m["sources_available"] = []
    m["sources_failed"] = []
    for w in results:
        if w is None:
            continue
        m["sources_available"].append(w.get("source", "unknown"))
        for f in ["current_temp", "max_temp", "min_temp", "weather_desc", "wind_direction", "wind_speed", "humidity", "rain_probability", "air_quality"]:
            if m[f] is None and w.get(f) is not None:
                m[f] = w[f]
    m["source"] = " + ".join(m["sources_available"]) if m["sources_available"] else None
    return m


def get_weather():
    log_info("=" * 40)
    log_info("开始获取天气数据...")
    results = []
    for name, f in [("Open-Meteo", fetch_openmeteo), ("wttr.in", fetch_wttr), ("墨迹天气", fetch_moji), ("和风天气", fetch_qweather)]:
        try:
            r = f()
            if r:
                results.append(r)
        except Exception as e:
            log_warning(f"{name} 异常: {e}")

    w = _merge(*results)
    if not w["sources_available"]:
        log_step("所有天气数据源均获取失败", False)
        w["all_failed"] = True
    else:
        log_step(f"天气获取完成 (数据源: {w['source']})", True)
        w["all_failed"] = False

    all_s = {"Open-Meteo", "wttr.in", "墨迹天气", "和风天气"}
    w["sources_failed"] = list(all_s - set(w["sources_available"]))
    log_info("=" * 40)
    return w
