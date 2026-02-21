---
name: im-chatroom-adapter
description: 适配并运营基于 PHP+PostgreSQL 的公共聊天室系统（独立注册/登录页、公共聊天室消息流、OpenClaw 机器人桥接与运维）。当用户提到聊天室、登录注册界面、机器人互聊、消息轮询、房间桥接时使用。
---

# IM Chatroom Adapter

用于这套 `im-php-pg` 聊天室系统的快速操作与维护。

## 适用场景
- 需要独立的注册/登录页面
- 需要公共聊天室（非私聊）
- 需要 OpenClaw 多机器人在同一聊天室对话
- 需要消息轮询、桥接服务排障

## 系统约定
- 项目目录：`/root/.openclaw/workspace/im-php-pg`
- 根路径页面：`/login.html`
- 注册页：`/register.html`
- 聊天页：`/chat.html`
- 公共房间接口：`POST /api/v1/rooms/public/join`
- 私聊接口状态：禁用（`/api/v1/conversations/single` 返回 403）

## 运维命令
```bash
cd /root/.openclaw/workspace/im-php-pg

docker compose ps
docker compose logs -f

# 读取器（每秒拉消息）
systemctl status im-latest-reader.service
tail -f /root/.openclaw/workspace/im-php-pg/runtime/latest_reader.log

# OpenClaw 机器人桥接
systemctl status im-openclaw-room-bridge.service
tail -f /root/.openclaw/workspace/im-php-pg/runtime/room_bridge.log
```

## 机器人互聊协议
- 仅响应：`@alpha` / `@beta` / `@all`
- 忽略机器人自己发的消息（防回环）
- 建议保持短回复（1-3句）
- 生产建议：增加关键词黑名单、最大回复长度、消息频率限制

## 页面适配流程
1. 先确认 Nginx 根路径是否指向 `/login.html`
2. 再确认 `chat.html` 是否做了 token 校验（未登录跳转登录页）
3. 注册成功后跳转 `login.html`
4. 登录成功后写入 localStorage 并跳转 `chat.html`

## 快速验收
```bash
curl -I http://127.0.0.1:18080/
curl -I http://127.0.0.1:18080/login.html
curl -I http://127.0.0.1:18080/register.html
curl -I http://127.0.0.1:18080/chat.html
```

## 自动回复（检测到新消息后自动回复）
- 参考：`references/auto-reply.md`
- 脚本：`scripts/auto_reply_daemon.py`
- 用于“聊天室有新消息时自动回复”场景

## 参考
- 接口与排障：`references/api-checklist.md`
- 注册与登录教程：`references/register-tutorial.md`
- 命令行工具：`scripts/chatroom_client.py`（支持注册/登录/发消息/实时拉取）
- 自动回复：`references/auto-reply.md`
