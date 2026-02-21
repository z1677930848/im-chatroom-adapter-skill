# API & 运行检查清单

## 页面
- `/` → `login.html`
- `/register.html` 可打开
- `/chat.html` 未登录应跳转到 `/login.html`

## 核心接口
- `GET /api/v1/health`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/rooms/public/join`
- `POST /api/v1/messages/send`
- `GET /api/v1/messages/pull`
- `POST /api/v1/messages/read`

## 禁用项
- `POST /api/v1/conversations/single` 应返回 403

## 服务
- `im-latest-reader.service` active
- `im-openclaw-room-bridge.service` active

## 常见问题
1. 公网打不开：检查安全组端口 18080
2. 登录后报 unauthorized：token 失效，清空 localStorage 后重新登录
3. 机器人不回复：检查消息是否带 @alpha/@beta/@all
