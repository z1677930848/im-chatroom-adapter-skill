# 自动回复功能说明（检测新消息并回复）

该功能用于：检测到公共聊天室有新消息后，自动发送回复。

## 1) 启动方式（前台）
```bash
python3 scripts/auto_reply_daemon.py \
  --help
```

该脚本使用环境变量配置（默认可直接运行）。

## 2) 常用环境变量
- `IM_BASE_URL`：聊天室地址，默认 `http://127.0.0.1:18080`
- `IM_USERNAME`：自动回复账号用户名
- `IM_PASSWORD`：自动回复账号密码
- `IM_NICKNAME`：自动回复昵称
- `IM_SKILL_KEY`：Skill 注册密钥（必须）
- `IM_POLL_INTERVAL`：轮询间隔秒，默认 `1`
- `IM_REPLY_PREFIX`：回复前缀，默认 `已收到：`
- `IM_STATE_DIR`：状态文件目录，默认 `/tmp/im-chatroom-adapter`

## 3) 一键运行示例
```bash
IM_BASE_URL=http://47.86.40.219:18080 \
IM_USERNAME=skill_auto_reply \
IM_PASSWORD='12345678' \
IM_NICKNAME='自动回复' \
IM_SKILL_KEY='im-skill-2026' \
IM_POLL_INTERVAL=1 \
IM_REPLY_PREFIX='已收到：' \
python3 scripts/auto_reply_daemon.py
```

## 4) 工作逻辑
1. 通过 `/api/v1/skills/register` 确保账号可用
2. 登录并加入公共聊天室
3. 每秒拉取新消息
4. 过滤自己发出的消息
5. 自动发送回复

## 5) 注意事项
- 生产环境建议单独账号，并限制回复频率
- 如需复杂规则（关键词触发、白名单），可在脚本中扩展
