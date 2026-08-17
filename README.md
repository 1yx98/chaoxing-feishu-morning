# 🌅 超星学习通 + 鄠邑校区天气 → 飞书早安推送

每天早上 06:00，GitHub Actions 自动运行，获取你的超星课程表 + 西安石油大学鄠邑校区天气，生成一张漂亮的飞书卡片发到你的飞书。

> **全程不需要你的电脑开机，不需要付费服务器，全部免费。**

---

## 📁 项目文件结构

```
chaoxing-feishu-morning/
├── .github/workflows/morning.yml    # GitHub Actions 定时任务
├── src/
│   ├── main.py                      # 主入口
│   ├── chaoxing.py                  # 超星登录 + 课程获取
│   ├── weather.py                   # 天气（多源容错）
│   ├── feishu.py                    # 飞书卡片消息
│   ├── config.py                    # 配置管理
│   └── utils.py                     # 工具函数
├── requirements.txt                 # 仅 2 个依赖
├── config.example.json              # 配置示例
├── .gitignore
└── README.md
```

---

## 🚀 小白完整部署教程

### 第一步：创建飞书应用

> 这是全新搭建，不要使用以前的飞书应用。

1. 打开 https://open.feishu.cn ，用飞书扫码登录
2. 点击「开发者后台」→「创建企业自建应用」
3. 应用名称填 `校园早安助手`，点击「创建」
4. 左侧「添加应用能力」→ 添加「机器人」
5. 左侧「权限管理」→ 搜索「消息」→ 开通：
   - `im:message`
   - `im:message:send_as_bot`
6. 左侧「凭证与基础信息」→ 记录 **App ID** 和 **App Secret**
7. 左侧「应用发布」→ 创建版本 → 申请发布

---

### 第二步：获取飞书 Chat ID

1. 在飞书里建一个群，把「校园早安助手」机器人拉进群
2. 在群里发一条消息
3. 回到飞书开放平台 →「开发调试」→「API 调试」
4. 找到「消息」→「获取会话列表」→ 发送请求
5. 复制返回的 `chat_id`（以 `oc_` 开头）

---

### 第三步：设置 GitHub Secrets

打开 https://github.com/1yx98/chaoxing-feishu-morning/settings/secrets/actions

点击「New repository secret」，逐个添加：

| Name | 填什么 |
|------|--------|
| `FEISHU_APP_ID` | 飞书 App ID（cli_开头） |
| `FEISHU_APP_SECRET` | 飞书 App Secret |
| `FEISHU_RECEIVE_ID` | 群的 Chat ID（oc_开头） |
| `FEISHU_RECEIVE_ID_TYPE` | `chat_id` |
| `CHAOXING_USERNAME` | 超星账号（手机号/学号） |
| `CHAOXING_PASSWORD` | 超星密码 |
| `TERM_START_DATE` | 开学日期，如 `2026-08-25`（可选） |
| `QWEATHER_API_KEY` | 和风天气 Key（可选） |

---

### 第四步：手动测试

1. 打开 https://github.com/1yx98/chaoxing-feishu-morning/actions
2. 点击左侧「早安推送」
3. 点击右侧「Run workflow」→ 绿色「Run workflow」
4. 等运行完成后，检查飞书是否收到卡片

---

### 第五步：定时运行

部署成功后，每天 **北京时间 06:00** 自动运行。你不需要做任何操作。

---

## 🔒 安全提醒

- ❌ 不要把账号密码写进代码
- ❌ 不要把 App Secret 发给任何人
- ✅ 所有敏感信息通过 GitHub Secrets 管理

---

## 📝 技术说明

- **语言**：Python 3.12+
- **运行平台**：GitHub Actions (Ubuntu)
- **超星登录**：AES-CBC 加密 + fanyalogin 接口
- **天气数据**：Open-Meteo（免费）+ wttr.in（免费）+ 和风天气（可选）
- **飞书消息**：App ID + App Secret → tenant_access_token → 卡片消息 API
- **卡片格式**：飞书卡片 JSON 2.0
