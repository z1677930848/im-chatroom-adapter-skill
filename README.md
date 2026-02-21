# PHP + PostgreSQL 即时通讯（IM）API 项目

本项目实现了一个精简可用的 IM 后端：
- API 注册账号
- API 登录（JWT）
- 创建单聊会话
- 发送消息
- 拉取消息（增量）
- 标记已读
- 获取会话列表（含未读数）

> 技术栈：PHP 8.2+（原生） + PostgreSQL 15+

---

## 目录结构

```text
im-php-pg/
  .env.example
  database/
    schema.sql
  public/
    index.php
  src/
    auth_middleware.php
    db.php
    env.php
    http.php
    jwt.php
  DEPLOY.md
  README.md
```

---

## 快速开始

1) 复制环境变量

```bash
cp .env.example .env
```

2) 修改 `.env` 的数据库和 JWT 配置

3) 创建数据库并导入表结构

```bash
psql -U postgres -c "CREATE DATABASE im_app;"
psql -U postgres -c "CREATE USER im_user WITH PASSWORD 'change_me';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE im_app TO im_user;"
psql -U postgres -d im_app -f database/schema.sql
```

4) 启动服务

```bash
php -S 0.0.0.0:8080 -t public
```

5) 健康检查

```bash
curl http://127.0.0.1:8080/api/v1/health
```

---

## API 示例

### 注册

```bash
curl -X POST http://127.0.0.1:8080/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"12345678","nickname":"Alice"}'
```

### 登录

```bash
curl -X POST http://127.0.0.1:8080/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"12345678"}'
```

拿到 token 后：

```bash
TOKEN="你的token"
```

### 创建单聊

```bash
curl -X POST http://127.0.0.1:8080/api/v1/conversations/single \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"target_user_id":2}'
```

### 发送消息

```bash
curl -X POST http://127.0.0.1:8080/api/v1/messages/send \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"conversation_id":1,"content":"你好","client_msg_id":"c_001"}'
```

### 拉取消息

```bash
curl "http://127.0.0.1:8080/api/v1/messages/pull?conversation_id=1&after_message_id=0&limit=50" \
  -H "Authorization: Bearer $TOKEN"
```

### 标记已读

```bash
curl -X POST http://127.0.0.1:8080/api/v1/messages/read \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"conversation_id":1,"last_read_message_id":100}'
```

### 会话列表

```bash
curl http://127.0.0.1:8080/api/v1/conversations/list \
  -H "Authorization: Bearer $TOKEN"
```

---

## 注意事项

- 生产环境请更换 `JWT_SECRET`
- 建议通过 Nginx + PHP-FPM 部署，不要直接暴露 `php -S`
- 建议加 HTTPS、限流、日志审计
