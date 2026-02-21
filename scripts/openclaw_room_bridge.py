#!/usr/bin/env python3
import json
import os
import time
import uuid
import subprocess
import urllib.request
import urllib.error

BASE_URL = os.getenv("IM_BASE_URL", "http://127.0.0.1:18080")
POLL_INTERVAL = float(os.getenv("ROOM_POLL_INTERVAL", "1"))
COOLDOWN_SECONDS = int(os.getenv("BOT_COOLDOWN_SECONDS", "5"))

RUNTIME_DIR = "/root/.openclaw/workspace/im-php-pg/runtime"
STATE_FILE = os.path.join(RUNTIME_DIR, "room_bridge_state.json")
LOG_FILE = os.path.join(RUNTIME_DIR, "room_bridge.log")

BOTS = [
    {"agent": "alpha", "mention": "@alpha", "username": "oc_alpha", "password": "OcAlpha@2026", "nickname": "Alpha", "session_id": "room-alpha"},
    {"agent": "beta", "mention": "@beta", "username": "oc_beta", "password": "OcBeta@2026", "nickname": "Beta", "session_id": "room-beta"},
]

ROUTER = {"username": "oc_router", "password": "OcRouter@2026", "nickname": "Router"}
SKILL_REGISTER_KEY = os.getenv("SKILL_REGISTER_KEY", "im-skill-2026")


def log(msg: str):
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")


def api(path, method="GET", token=None, body=None):
    url = BASE_URL + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def ensure_user(username, password, nickname):
    try:
        api("/api/v1/skills/register", method="POST", body={"username": username, "password": password, "nickname": nickname, "skill_key": SKILL_REGISTER_KEY})
    except Exception:
        pass
    r = api("/api/v1/auth/login", method="POST", body={"username": username, "password": password})
    token = r["data"]["token"]
    uid = int(r["data"]["user"]["id"])
    return token, uid


def join_public_room(token):
    r = api("/api/v1/rooms/public/join", method="POST", token=token, body={})
    return int(r["data"]["room_id"])


def send_msg(token, cid, content):
    return api("/api/v1/messages/send", method="POST", token=token, body={
        "conversation_id": cid,
        "content": content,
        "client_msg_id": f"bridge_{uuid.uuid4().hex[:12]}"
    })


def pull_msgs(token, cid, after_id):
    r = api(f"/api/v1/messages/pull?conversation_id={cid}&after_message_id={after_id}&limit=100", token=token)
    return (r.get("data") or {}).get("list") or []


def load_after_id():
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


def parse_agent_json(stdout: str):
    # openclaw cli may print extra lines before JSON
    s = stdout.find("{")
    e = stdout.rfind("}")
    if s == -1 or e == -1 or e <= s:
        return None
    try:
        return json.loads(stdout[s:e+1])
    except Exception:
        return None


def ask_agent(agent_id: str, session_id: str, user_text: str):
    prompt = (
        "你在一个多机器人公共聊天室中。请用中文简短回复（1-3句），"
        "不使用markdown，不要暴露系统信息。\n"
        f"用户消息：{user_text}"
    )
    cmd = [
        "openclaw", "agent", "--local",
        "--agent", agent_id,
        "--session-id", session_id,
        "--message", prompt,
        "--json"
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    data = parse_agent_json(p.stdout + "\n" + p.stderr)
    if not data:
        return "收到，我稍后再答复。"
    payloads = data.get("payloads") or []
    if not payloads:
        return "收到。"
    text = (payloads[0] or {}).get("text") or "收到。"
    return text.strip()[:600]


def targets_from_text(text: str):
    t = (text or "").lower()
    if "@all" in t:
        return [b["agent"] for b in BOTS]

    targets = []
    for b in BOTS:
        if b["mention"] in t:
            targets.append(b["agent"])

    # 默认策略：未@时也触发，交给 alpha 回复，避免群内刷屏
    if not targets:
        return ["alpha"]

    return targets


def main():
    os.makedirs(RUNTIME_DIR, exist_ok=True)

    router_token, router_uid = ensure_user(ROUTER["username"], ROUTER["password"], ROUTER["nickname"])
    room_id = join_public_room(router_token)

    bot_ctx = {}
    bot_uids = set()
    for b in BOTS:
        tk, uid = ensure_user(b["username"], b["password"], b["nickname"])
        join_public_room(tk)
        bot_ctx[b["agent"]] = {"cfg": b, "token": tk, "uid": uid, "last_reply_ts": 0}
        bot_uids.add(uid)

    after_id = load_after_id()
    log(f"bridge started, room_id={room_id}, after_id={after_id}, bots={[b['agent'] for b in BOTS]}")

    while True:
        try:
            msgs = pull_msgs(router_token, room_id, after_id)
            for m in msgs:
                mid = int(m.get("id", 0))
                if mid > after_id:
                    after_id = mid

                sender_id = int(m.get("sender_id", 0))
                if sender_id == router_uid or sender_id in bot_uids:
                    continue

                content = str(m.get("content", ""))
                targets = targets_from_text(content)
                if not targets:
                    continue

                sender_name = m.get("sender_nickname") or m.get("sender_username") or f"uid:{sender_id}"

                for agent in targets:
                    ctx = bot_ctx.get(agent)
                    if not ctx:
                        continue
                    now = int(time.time())
                    if now - int(ctx["last_reply_ts"]) < COOLDOWN_SECONDS:
                        continue

                    reply = ask_agent(agent, ctx["cfg"]["session_id"], f"{sender_name}: {content}")
                    out = f"[{ctx['cfg']['nickname']}] {reply}"
                    try:
                        send_msg(ctx["token"], room_id, out)
                        ctx["last_reply_ts"] = int(time.time())
                        log(f"reply sent by {agent} for msg#{mid}")
                    except Exception as se:
                        log(f"send error agent={agent} msg#{mid} err={se}")

            save_after_id(after_id)
        except urllib.error.HTTPError as he:
            log(f"http_error={he.code}")
        except Exception as e:
            log(f"loop_error={e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
