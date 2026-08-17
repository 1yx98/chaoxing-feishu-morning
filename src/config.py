"""
配置管理模块
所有配置项优先从环境变量读取，方便 GitHub Actions Secrets 注入。
"""

import os

# ============================================================
# 飞书应用配置
# ============================================================
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "").strip()
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "").strip()

# 飞书消息接收者 ID（Chat ID 或 User ID）
FEISHU_RECEIVE_ID = os.getenv("FEISHU_RECEIVE_ID", "").strip()
# 接收者类型：chat_id（群聊）或 open_id（个人）
FEISHU_RECEIVE_ID_TYPE = os.getenv("FEISHU_RECEIVE_ID_TYPE", "chat_id").strip()

# 飞书 API 基础地址
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"

# ============================================================
# 超星学习通配置
# ============================================================
CHAOXING_USERNAME = os.getenv("CHAOXING_USERNAME", "").strip()
CHAOXING_PASSWORD = os.getenv("CHAOXING_PASSWORD", "").strip()

# 超星登录相关 API
CHAOXING_LOGIN_URL = "https://passport2.chaoxing.com/fanyalogin"
CHAOXING_PRELOGIN_URL = "https://passport2.chaoxing.com/login?fid=&newversion=true&refer=https://i.chaoxing.com"
CHAOXING_COURSE_URL = "https://mooc1-api.chaoxing.com/mycourse/backclazzdata?view=json&rss=1"
CHAOXING_SCHEDULE_URL = "https://kb.chaoxing.com/pc/curriculum/getMyLessons"

# AES 加密密钥（超星 fanyalogin 接口使用）
CHAOXING_AES_KEY = "u2oh6Vu^HWe4_AES"

# ============================================================
# 天气配置
# ============================================================
# 鄠邑区城市代码
WEATHER_CITY_ID = os.getenv("WEATHER_CITY_ID", "101110106").strip()
WEATHER_CITY_NAME = "西安石油大学鄠邑校区"

# 和风天气 API Key（可选）
QWEATHER_API_KEY = os.getenv("QWEATHER_API_KEY", "").strip()

# ============================================================
# 课程时间表（西安石油大学标准作息）
# ============================================================
COURSE_TIME_TABLE = {
    1:  {"name": "第1节",  "start": "08:00", "end": "08:45"},
    2:  {"name": "第2节",  "start": "08:55", "end": "09:40"},
    3:  {"name": "第3节",  "start": "10:00", "end": "10:45"},
    4:  {"name": "第4节",  "start": "10:55", "end": "11:40"},
    5:  {"name": "第5节",  "start": "14:00", "end": "14:45"},
    6:  {"name": "第6节",  "start": "14:55", "end": "15:40"},
    7:  {"name": "第7节",  "start": "16:00", "end": "16:45"},
    8:  {"name": "第8节",  "start": "16:55", "end": "17:40"},
    9:  {"name": "第9节",  "start": "19:00", "end": "19:45"},
    10: {"name": "第10节", "start": "19:55", "end": "20:40"},
}

# ============================================================
# 请求配置
# ============================================================
REQUEST_TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
