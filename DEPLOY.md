# 部署教程（Ubuntu 22.04 / Debian 12）

本文档演示如何在 Linux 服务器部署 `im-php-pg`。

## 1. 安装基础环境

```bash
sudo apt update
sudo apt install -y php php-cli php-pgsql php-fpm postgresql postgresql-contrib nginx
```

检查版本：

```bash
php -v
psql --version
nginx -v
```

---

## 2. 部署代码

假设项目目录：`/opt/im-php-pg`

```bash
sudo mkdir -p /opt/im-php-pg
sudo cp -r /root/.openclaw/workspace/im-php-pg/* /opt/im-php-pg/
sudo chown -R www-data:www-data /opt/im-php-pg
```

---

## 3. 初始化 PostgreSQL

切换 postgres 用户：

```bash
sudo -u postgres psql
```

在 psql 中执行：

```sql
CREATE DATABASE im_app;
CREATE USER im_user WITH PASSWORD 'change_me';
GRANT ALL PRIVILEGES ON DATABASE im_app TO im_user;
\q
```

导入表结构：

```bash
psql -h 127.0.0.1 -U im_user -d im_app -f /opt/im-php-pg/database/schema.sql
```

---

## 4. 配置环境变量

```bash
sudo cp /opt/im-php-pg/.env.example /opt/im-php-pg/.env
sudo nano /opt/im-php-pg/.env
```

至少修改：
- `DB_PASS`
- `JWT_SECRET`
- `APP_URL`

---

## 5. 配置 Nginx

创建站点配置：

```bash
sudo nano /etc/nginx/sites-available/im-php-pg.conf
```

写入以下内容（按你的 php-fpm 版本调整 sock 路径）：

```nginx
server {
    listen 80;
    server_name your-domain-or-ip;

    root /opt/im-php-pg/public;
    index index.php;

    location / {
        try_files $uri /index.php?$query_string;
    }

    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        fastcgi_pass unix:/run/php/php8.2-fpm.sock;
    }

    location ~ /\. {
        deny all;
    }
}
```

启用站点：

```bash
sudo ln -s /etc/nginx/sites-available/im-php-pg.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl restart php8.2-fpm
```

---

## 6. 防火墙（可选）

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## 7. 接口验证

```bash
curl http://your-domain-or-ip/api/v1/health
```

返回 `code=0` 即成功。

---

## 8. 生产建议

1. 配置 HTTPS（Let's Encrypt）
2. 设置日志轮转（Nginx + 应用日志）
3. 在 Nginx 或网关做限流
4. 定期备份 PostgreSQL
5. 将 JWT_SECRET 放入更安全的密钥管理系统
