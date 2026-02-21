#!/usr/bin/env python3
"""
OpenClaw 聊天室自动回复服务
- 监听公共聊天室消息
- 调用主代理生成智能回复
- 支持状态持久化，避免重复回复
"""

import json
import os
import time
import uuid
import subprocess
import urllib.request
import urllib.error
import logging
from datetime import datetime

# ============ 配置 ============
BASE_URL = os.getenv("IM_BASE_URL", "http://127.0.0.1:18080")
USERNAME = os.getenv("IM_USERNAME", "zhouzhou_reply")
PASSWORD = os.getenv("IM_PASSWORD", "12345678")
NICKNAME = os.getenv("IM_NICKNAME", "周周")
SKILL_KEY = os.getenv("IM_SKILL_KEY", "im-skill-2026")

POLL_INTERVAL = float(os.getenv("IM_POLL_INTERVAL", "1"))
STATE_DIR = os.getenv("IM_STATE_DIR", "/root/.openclaw/workspace/im-php-pg/runtime")
STATE_FILE = os.path.join(STATE_DIR, "main_reply_state.json")
LOG_FILE = os.path.join(STATE_DIR, "main_reply.log")

SESSION_ID = os.getenv("IM_AGENT_SESSION_ID", "room-main-live")
RUN_ONCE = os.getenv("IM_RUN_ONCE", "0").strip().lower() in {"1", "true", "yes", "on"}

# 增加超时时间，避免 GLM5 等模型响应慢导致兜底回复
AGENT_TIMEOUT = int(os.getenv("IM_AGENT_TIMEOUT", "60"))

# 每次拉取与处理上限
PULL_LIMIT = int(os.getenv("IM_PULL_LIMIT", "30"))
MAX_MESSAGES_PER_RUN = int(os.getenv("IM_MAX_MESSAGES_PER_RUN", "3"))

# 避免重启或异常导致重复回复：记录最近已回复的消息ID
REPLIED_CACHE_LIMIT = int(os.getenv("IM_REPLIED_CACHE_LIMIT", "600"))

# 避免自己回复自己的消息
IGNORE_USERNAMES = {"zhouzhou_reply", "oc_alpha", "oc_beta", "oc_router"}

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============ API 调用 ============
def api(path, method="GET", token=None, body=None):
    url = BASE_URL.rstrip("/") + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ensure_user():
    try:
        api("/api/v1/skills/register", method="POST", body={
            "username": USERNAME,
            "password": PASSWORD,
            "nickname": NICKNAME,
            "skill_key": SKILL_KEY,
        })
    except Exception as e:
        logger.debug(f"注册用户（可能已存在）: {e}")
    
    r = api("/api/v1/auth/login", method="POST", body={
        "username": USERNAME,
        "password": PASSWORD,
    })
    return r["data"]["token"], int(r["data"]["user"]["id"])


def join_room(token):
    r = api("/api/v1/rooms/public/join", method="POST", token=token, body={})
    return int(r["data"]["room_id"])


# ============ 状态管理 ============
def load_state():
    os.makedirs(STATE_DIR, exist_ok=True)
    if not os.path.exists(STATE_FILE):
        logger.info("状态文件不存在，从头开始")
        return 0, set(), []
    
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            s = json.load(f)
        after_id = int(s.get("after_id", 0))
        replied_ids = s.get("replied_ids", [])
        
        if not isinstance(replied_ids, list):
            replied_ids = []
        
        ordered = []
        seen = set()
        for x in replied_ids:
            try:
                mid = int(x)
            except Exception:
                continue
            if mid in seen:
                continue
            seen.add(mid)
            ordered.append(mid)
        
        if len(ordered) > REPLIED_CACHE_LIMIT:
            ordered = ordered[-REPLIED_CACHE_LIMIT:]
        
        logger.info(f"加载状态: after_id={after_id}, replied_count={len(ordered)}")
        return after_id, set(ordered), ordered
    except Exception as e:
        logger.error(f"加载状态失败: {e}")
        return 0, set(), []


def save_state(after_id, replied_order):
    payload = {
        "after_id": int(after_id),
        "replied_ids": replied_order[-REPLIED_CACHE_LIMIT:],
        "updated_at": datetime.now().isoformat()
    }
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存状态失败: {e}")


# ============ 主代理调用 ============
def parse_agent_output(output: str):
    """解析 openclaw agent --json 的输出"""
    if not output:
        return None
    
    # 尝试找到 JSON 对象
    lines = output.strip().split('\n')
    for line in reversed(lines):  # 从后往前找
        line = line.strip()
        if line.startswith('{'):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    
    # 尝试找到第一个 { 和最后一个 }
    s = output.find('{')
    e = output.rfind('}')
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(output[s:e+1])
        except json.JSONDecodeError:
            pass
    
    return None


def ask_main_agent(sender: str, content: str) -> str:
    """调用主代理生成回复"""
    prompt = (
        f"你在公共聊天室中，用户 {sender} 发送了消息。"
        f"请用中文简洁回复（1-2句），语气专业友好，不要使用markdown格式。"
        f"消息内容: {content}"
    )
    
    cmd = [
        "openclaw", "agent", "--local", "--agent", "main",
        "--session-id", SESSION_ID,
        "--message", prompt,
        "--json"
    ]
    
    logger.info(f"调用主代理: sender={sender}, content={content[:50]}...")
    
    try:
        p = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=AGENT_TIMEOUT
        )
        
        combined_output = (p.stdout or "") + "\n" + (p.stderr or "")
        data = parse_agent_output(combined_output)
        
        if not data:
            logger.warning(f"无法解析代理输出: stdout={p.stdout[:200] if p.stdout else 'empty'}")
            return None
        
        payloads = data.get("payloads") or []
        if not payloads:
            logger.warning("代理返回空 payloads")
            return None
        
        text = (payloads[0] or {}).get("text")
        if text:
            return text.strip()[:500]
        
        return None
        
    except subprocess.TimeoutExpired:
        logger.warning(f"代理调用超时 ({AGENT_TIMEOUT}s)")
        return None
    except Exception as e:
        logger.error(f"代理调用失败: {e}")
        return None


# ============ 消息发送 ============
def send_msg(token, room_id, text):
    return api("/api/v1/messages/send", method="POST", token=token, body={
        "conversation_id": room_id,
        "content": text,
        "client_msg_id": f"main_{uuid.uuid4().hex[:12]}"
    })


# ============ 主循环 ============
def run_once(token, my_uid, room_id, after_id, replied_set, replied_order):
    r = api(
        f"/api/v1/messages/pull?conversation_id={room_id}&after_message_id={after_id}&limit={PULL_LIMIT}",
        token=token,
    )
    items = (r.get("data") or {}).get("list") or []
    
    if not items:
        return after_id, replied_set, replied_order
    
    logger.info(f"拉取到 {len(items)} 条消息")
    
    handled = 0
    for m in items:
        mid = int(m.get("id", 0))
        after_id = max(after_id, mid)
        
        sender_id = int(m.get("sender_id", 0))
        if sender_id == my_uid:
            continue
        
        sender_username = str(m.get("sender_username") or "").strip().lower()
        if sender_username in IGNORE_USERNAMES:
            continue
        
        # 关键去重：同一消息ID只回复一次
        if mid in replied_set:
            continue
        
        sender = m.get("sender_nickname") or m.get("sender_username") or f"uid:{sender_id}"
        content = str(m.get("content", "")).strip()
        
        if not content:
            continue
        
        try:
            reply = ask_main_agent(sender, content)
            
            if reply:
                send_msg(token, room_id, reply)
                logger.info(f"已回复 {sender}: {reply[:50]}...")
            else:
                # 主代理返回空时，发送简单确认
                fallback = f"收到 {sender} 的消息，我稍后回复。"
                send_msg(token, room_id, fallback)
                logger.info(f"发送兜底回复: {fallback}")
            
            replied_set.add(mid)
            replied_order.append(mid)
            if len(replied_order) > REPLIED_CACHE_LIMIT:
                dropped = replied_order.pop(0)
                replied_set.discard(dropped)
            handled += 1
            
        except Exception as e:
            logger.error(f"处理消息 {mid} 失败: {e}")
        
        # 每条消息处理完即落盘
        save_state(after_id, replied_order)
        
        if handled >= MAX_MESSAGES_PER_RUN:
            break
    
    return after_id, replied_set, replied_order


def main():
    logger.info("=== 聊天室自动回复服务启动 ===")
    logger.info(f"BASE_URL={BASE_URL}")
    logger.info(f"AGENT_TIMEOUT={AGENT_TIMEOUT}s")
    
    token, my_uid = ensure_user()
    logger.info(f"登录成功: uid={my_uid}")
    
    room_id = join_room(token)
    logger.info(f"加入房间: room_id={room_id}")
    
    after_id, replied_set, replied_order = load_state()
    
    while True:
        try:
            after_id, replied_set, replied_order = run_once(
                token, my_uid, room_id, after_id, replied_set, replied_order
            )
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP 错误: {e}")
        except Exception as e:
            logger.error(f"运行错误: {e}")
        
        if RUN_ONCE:
            break
        
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
