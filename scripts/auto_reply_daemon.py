#!/usr/bin/env python3
import json
import os
import time
import uuid
import urllib.request
import urllib.error

BASE_URL = os.getenv("IM_BASE_URL", "http://127.0.0.1:18080")
USERNAME = os.getenv("IM_USERNAME", "skill_auto_reply")
PASSWORD = os.getenv("IM_PASSWORD", "12345678")
NICKNAME = os.getenv("IM_NICKNAME", "自动回复")
SKILL_KEY = os.getenv("IM_SKILL_KEY", "im-skill-2026")
POLL_INTERVAL = float(os.getenv("IM_POLL_INTERVAL", "1"))
REPLY_PREFIX = os.getenv("IM_REPLY_PREFIX", "已收到：")
RUN_ONCE = os.getenv("IM_RUN_ONCE", "0").strip().lower() in {"1", "true", "yes", "on"}

STATE_DIR = os.getenv("IM_STATE_DIR", "/tmp/im-chatroom-adapter")
STATE_FILE = os.path.join(STATE_DIR, "auto_reply_state.json")


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
    except Exception:
        pass

    r = api("/api/v1/auth/login", method="POST", body={
        "username": USERNAME,
        "password": PASSWORD,
    })
    token = r["data"]["token"]
    uid = int(r["data"]["user"]["id"])
    return token, uid


def join_room(token):
    r = api("/api/v1/rooms/public/join", method="POST", token=token, body={})
    return int(r["data"]["room_id"])


def load_after_id():
    os.makedirs(STATE_DIR, exist_ok=True)
    if not os.path.exists(STATE_FILE):
        return 0
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return int(json.load(f).get("after_id", 0))
    except Exception:
        return 0


def save_after_id(after_id):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"after_id": int(after_id)}, f)


def run_once(token, my_uid, room_id, after_id):
    r = api(f"/api/v1/messages/pull?conversation_id={room_id}&after_message_id={after_id}&limit=100", token=token)
    items = (r.get("data") or {}).get("list") or []

    for m in items:
        mid = int(m.get("id", 0))
        after_id = max(after_id, mid)

        sender_id = int(m.get("sender_id", 0))
        if sender_id == my_uid:
            continue

        content = str(m.get("content", "")).strip()
        if not content:
            continue

        reply = f"{REPLY_PREFIX}{content[:120]}"
        api("/api/v1/messages/send", method="POST", token=token, body={
            "conversation_id": room_id,
            "content": reply,
            "client_msg_id": f"auto_{uuid.uuid4().hex[:12]}"
        })

    save_after_id(after_id)
    return after_id


def main():
    token, my_uid = ensure_user()
    room_id = join_room(token)
    after_id = load_after_id()

    while True:
        try:
            after_id = run_once(token, my_uid, room_id, after_id)
        except urllib.error.HTTPError:
            pass
        except Exception:
            pass

        if RUN_ONCE:
            break

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
