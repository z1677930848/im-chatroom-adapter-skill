#!/usr/bin/env python3
import json
import os
import time
import urllib.request
import urllib.error

BASE_URL = os.getenv("IM_BASE_URL", "http://127.0.0.1:18080")
USERNAME = os.getenv("IM_USERNAME", "auto_tester")
PASSWORD = os.getenv("IM_PASSWORD", "12345678")
NICKNAME = os.getenv("IM_NICKNAME", "系统测试")

RUNTIME_DIR = "/root/.openclaw/workspace/im-php-pg/runtime"
STATE_FILE = os.path.join(RUNTIME_DIR, "latest_reader_state.json")
LOG_FILE = os.path.join(RUNTIME_DIR, "latest_reader.log")
SKILL_REGISTER_KEY = os.getenv("SKILL_REGISTER_KEY", "im-skill-2026")


def req(path, method="GET", token=None, body=None):
    url = BASE_URL + path
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=10) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def safe_register():
    try:
        req("/api/v1/skills/register", method="POST", body={
            "username": USERNAME,
            "password": PASSWORD,
            "nickname": NICKNAME,
            "skill_key": SKILL_REGISTER_KEY,
        })
    except Exception:
        pass


def login():
    r = req("/api/v1/auth/login", method="POST", body={
        "username": USERNAME,
        "password": PASSWORD,
    })
    return r["data"]["token"]


def join_public_room(token):
    r = req("/api/v1/rooms/public/join", method="POST", token=token, body={})
    return int(r["data"]["room_id"])


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                s = json.load(f)
                return int(s.get("after_id", 0))
        except Exception:
            return 0
    return 0


def save_state(after_id):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"after_id": int(after_id)}, f, ensure_ascii=False)


def append_log(line):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    safe_register()
    token = login()
    cid = join_public_room(token)
    after_id = load_state()
    append_log(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] reader started, room_id={cid}, after_id={after_id}")

    while True:
        try:
            r = req(f"/api/v1/messages/pull?conversation_id={cid}&after_message_id={after_id}&limit=50", token=token)
            items = (r.get("data") or {}).get("list") or []
            for m in items:
                mid = int(m.get("id", 0))
                sender = m.get("sender_nickname") or m.get("sender_username") or f"uid:{m.get('sender_id')}"
                content = str(m.get("content", "")).replace("\n", " ")
                append_log(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] id={mid} from={sender} msg={content}")
                if mid > after_id:
                    after_id = mid
            if items:
                save_state(after_id)
        except urllib.error.HTTPError as e:
            append_log(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] http_error={e.code}")
        except Exception as e:
            append_log(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] error={e}")

        time.sleep(1)


if __name__ == "__main__":
    main()
