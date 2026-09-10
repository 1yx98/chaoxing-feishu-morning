# 🌅 超星学习通 + 鄠邑校区天气 → 飞书早安推送 & 课程提醒

每天早上自动推送超星课程表 + 西安石油大学鄠邑校区天气到飞书，每节课前 20 分钟自动推送下一节课信息。

> **全程不需要电脑开机，不需要付费服务器，全部免费。**
>
> 定时触发由 [cron-job.org](https://cron-job.org)（免费外部定时服务）调用 GitHub API 实现，解决 GitHub Actions 免费账户高峰期 cron 延迟 1~2 小时的问题。

---

## ⏰ 你会收到通知的时间

| 通知 | 收到时间 | 内容 |
|------|---------|------|
| 早安推送 | 每天 5:46~5:47 | 当日课程表 + 鄠邑校区天气 |
| 第1节课程 | 周一至周五 8:00 | 下一节课信息（8:20 上课） |
| 第2节课程 | 周一至周五 10:00 | 下一节课信息（10:20 上课） |
| 第3节课程 | 周一至周五 13:40 | 下一节课信息（14:00 上课） |
| 第4节课程 | 周一至周五 15:40 | 下一节课信息（16:00 上课） |
| 第5节课程 | 周一至周五 18:40 | 下一节课信息（19:00 上课） |

课程时间表：第1节 08:20-10:00、第2节 10:20-12:00、第3节 14:00-15:40、第4节 16:00-17:40、第5节 19:00-20:40

---

## 📁 项目文件结构

```
chaoxing-feishu-morning/
├── .github/workflows/
│   ├── morning.yml                 # 早安推送 workflow（workflow_dispatch 触发）
│   └── class-reminder.yml          # 课程提醒 workflow（workflow_dispatch 触发）
├── src/
│   ├── main.py                     # 早安推送主入口
│   ├── class_reminder_single.py    # 课程提醒主入口（单次触发，自动识别课程）
│   ├── chaoxing.py                 # 超星登录 + 课程获取（含重试机制）
│   ├── weather.py                  # 天气（多源容错）
│   ├── feishu.py                   # 飞书卡片消息
│   ├── config.py                   # 配置管理
│   └── utils.py                    # 工具函数
├── requirements.txt                # 依赖
├── config.example.json             # 配置示例
├── .gitignore
└── README.md
```

> 旧文件 `class_reminder.py`、`class_reminder_loop.py` 已保留未使用，供参考。

---

## 🔧 定时方案说明

### 为什么不用 GitHub Actions 自带 cron？

GitHub Actions 免费账户在北京时间凌晨 5~10 点（UTC 21:00~2:00）是全球最高峰期，调度延迟 1~2 小时是常态，导致推送不准时。

### 当前方案：cron-job.org + GitHub API

[cron-job.org](https://cron-job.org) 是免费的外部定时服务，在设定时间精确调用 GitHub API 触发 `workflow_dispatch`，绕过 GitHub Actions 的调度队列。

**cron-job.org 上配置了 6 个定时任务：**

| 任务名称 | Cron 表达式（北京时间） | 触发的 workflow |
|---------|----------------------|----------------|
| 早安推送 | `45 5 * * *` | morning.yml |
| 第1节提醒 | `35 7 * * 1-5` | class-reminder.yml |
| 第2节提醒 | `35 9 * * 1-5` | class-reminder.yml |
| 第3节提醒 | `15 13 * * 1-5` | class-reminder.yml |
| 第4节提醒 | `15 15 * * 1-5` | class-reminder.yml |
| 第5节提醒 | `15 18 * * 1-5` | class-reminder.yml |

每个任务通过 POST 请求调用 GitHub API：
```
POST https://api.github.com/repos/1yx98/chaoxing-feishu-morning/actions/workflows/{workflow}/dispatches
Headers:
  Accept: application/vnd.github+json
  Authorization: Bearer {GitHub Personal Access Token}
  Content-Type: application/json
Body: {"ref":"main"}
```

课程提醒触发后，脚本自动识别未来 50 分钟内的课程，sleep 到课前 20 分钟准时发送；若启动时已上课但不超过 30 分钟，仍会补发。

---

## 🚀 小白完整部署教程

### 第一步：创建飞书应用

1. 打开 https://open.feishu.cn ，用飞书扫码登录
2. 点击「开发者后台」→「创建企业自建应用」
3. 应用名称填 `校园早安助手`，点击「创建」
4. 左侧「添加应用能力」→ 添加「机器人」
5. 左侧「权限管理」→ 搜索「消息」→ 开通：
   - `im:message`
   - `im:message:send_as_bot`
6. 左侧「凭证与基础信息」→ 记录 **App ID** 和 **App Secret**
7. 左侧「应用发布」→ 创建版本 → 申请发布

### 第二步：获取飞书 Chat ID

1. 在飞书里建一个群，把「校园早安助手」机器人拉进群
2. 在群里发一条消息
3. 回到飞书开放平台 →「开发调试」→「API 调试」
4. 找到「消息」→「获取会话列表」→ 发送请求
5. 复制返回的 `chat_id`（以 `oc_` 开头）

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

### 第四步：创建 GitHub Personal Access Token

1. 打开 https://github.com/settings/tokens
2. 点击「Generate new token」→「Generate new token (classic)」
3. Note 填 `cron-job-trigger`，Expiration 选 `30 days`（建议定期轮换）
4. 勾选 `repo` 权限
5. 点击「Generate token」，**复制保存 token 值**（只显示一次）

### 第五步：配置 cron-job.org 定时任务

1. 打开 https://cron-job.org 注册账号并登录
2. 点击「CREATE CRONJOB」，按上表创建 6 个任务
3. 每个任务的 ADVANCED 标签页配置：
   - Request method: `POST`
   - Headers: 添加 3 个（Accept、Authorization、Content-Type，见上方 API 示例）
   - Request body: `{"ref":"main"}`
   - Time zone: `Asia/Shanghai`
4. 建议开启「Notify me when execution of the cronjob fails」失败邮件通知
5. 点击「Create」保存

### 第六步：手动测试

1. 打开 https://github.com/1yx98/chaoxing-feishu-morning/actions
2. 点击左侧「早安推送」或「课前提醒」
3. 点击右侧「Run workflow」→ 绿色「Run workflow」
4. 等运行完成后，检查飞书是否收到消息

---

## 📋 日志查看

每次运行的日志会通过 `actions/upload-artifact@v4` 上传，保留 30 天。

查看方式：
1. 打开 https://github.com/1yx98/chaoxing-feishu-morning/actions
2. 点击某次运行记录
3. 页面底部「Artifacts」区域下载日志文件

---

## 🔒 安全提醒

- ❌ 不要把账号密码写进代码
- ❌ 不要把 App Secret、GitHub Token 发给任何人
- ✅ 所有敏感信息通过 GitHub Secrets 管理
- ✅ GitHub Token 仅用于触发 workflow，最小权限（repo）即可
- ✅ 建议 Token 设置 30~90 天过期，定期轮换

---

## 📝 技术说明

- **语言**：Python 3.12+
- **运行平台**：GitHub Actions (Ubuntu)
- **定时触发**：cron-job.org → GitHub API → workflow_dispatch
- **超星登录**：AES-CBC 加密 + fanyalogin 接口，含 3 次自动重试
- **课程提醒**：自动识别未来 50 分钟内课程，精确 sleep 到课前 20 分钟，上课 30 分钟内补发兜底
- **天气数据**：Open-Meteo（免费）+ wttr.in（免费）+ 和风天气（可选）
- **飞书消息**：App ID + App Secret → tenant_access_token → 卡片消息 API
- **卡片格式**：飞书卡片 JSON 2.0
- **失败通知**：课程提醒获取课程失败、发送失败、程序异常时主动发飞书通知
