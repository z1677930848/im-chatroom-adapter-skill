# 注册与登录教程（聊天室版）

## 1) 打开页面
- 登录页：`http://<服务器IP>:18080/login.html`
- 注册页：`http://<服务器IP>:18080/register.html`

## 2) 注册账号
在注册页填写：
- 用户名（3-50）
- 昵称
- 密码（至少8位）

注册成功后会自动跳到登录页。

## 3) 登录并进入聊天室
在登录页输入用户名和密码，点击“登录并进入聊天室”。
系统会自动：
1. 获取 token
2. 加入公共聊天室
3. 跳转到 `chat.html`

## 4) 发送消息
进入聊天室后：
- 输入内容
- 点击发送（或 Enter）

## 5) 实时获取消息
- 前端页面默认每 2 秒自动刷新
- 如果需要 1 秒级实时拉取，可使用 CLI tail：

```bash
python3 skills/im-chatroom-adapter/scripts/chatroom_client.py \
  --base-url http://127.0.0.1:18080 \
  tail --token <TOKEN> --room-id <ROOM_ID> --after-id 0 --interval 1
```
