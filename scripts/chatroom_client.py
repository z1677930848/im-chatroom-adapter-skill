#!/usr/bin/env python3
import argparse
import json
import sys
import time
import urllib.request
import urllib.error


def api(base_url, path, method="GET", token=None, body=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def cmd_register(args):
    body = {
        "username": args.username,
        "password": args.password,
        "nickname": args.nickname or args.username,
        "skill_key": args.skill_key,
    }
    r = api(args.base_url, "/api/v1/skills/register", method="POST", body=body)
    print(json.dumps(r, ensure_ascii=False))


def cmd_login(args):
    r = api(args.base_url, "/api/v1/auth/login", method="POST", body={
        "username": args.username,
        "password": args.password,
    })
    print(json.dumps(r, ensure_ascii=False))


def cmd_join(args):
    r = api(args.base_url, "/api/v1/rooms/public/join", method="POST", token=args.token, body={})
    print(json.dumps(r, ensure_ascii=False))


def cmd_send(args):
    body = {
        "conversation_id": int(args.room_id),
        "content": args.content,
        "client_msg_id": args.client_msg_id or f"cli_{int(time.time() * 1000)}",
    }
    r = api(args.base_url, "/api/v1/messages/send", method="POST", token=args.token, body=body)
    print(json.dumps(r, ensure_ascii=False))


def cmd_pull(args):
    path = f"/api/v1/messages/pull?conversation_id={int(args.room_id)}&after_message_id={int(args.after_id)}&limit={int(args.limit)}"
    r = api(args.base_url, path, method="GET", token=args.token)
    print(json.dumps(r, ensure_ascii=False))


def cmd_tail(args):
    after_id = int(args.after_id)
    while True:
        try:
            path = f"/api/v1/messages/pull?conversation_id={int(args.room_id)}&after_message_id={after_id}&limit=100"
            r = api(args.base_url, path, method="GET", token=args.token)
            items = (r.get("data") or {}).get("list") or []
            for m in items:
                mid = int(m.get("id", 0))
                sender = m.get("sender_nickname") or m.get("sender_username") or f"uid:{m.get('sender_id')}"
                print(f"[{m.get('created_at')}] #{mid} {sender}: {m.get('content')}")
                after_id = max(after_id, mid)
        except urllib.error.HTTPError as e:
            print(f"http_error={e.code}", file=sys.stderr)
        except Exception as e:
            print(f"error={e}", file=sys.stderr)
        time.sleep(float(args.interval))


def build_parser():
    p = argparse.ArgumentParser(description="IM Chatroom CLI helper")
    p.add_argument("--base-url", default="http://127.0.0.1:18080")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("register")
    sp.add_argument("--username", required=True)
    sp.add_argument("--password", required=True)
    sp.add_argument("--nickname", default="")
    sp.add_argument("--skill-key", required=True)
    sp.set_defaults(func=cmd_register)

    sp = sub.add_parser("login")
    sp.add_argument("--username", required=True)
    sp.add_argument("--password", required=True)
    sp.set_defaults(func=cmd_login)

    sp = sub.add_parser("join")
    sp.add_argument("--token", required=True)
    sp.set_defaults(func=cmd_join)

    sp = sub.add_parser("send")
    sp.add_argument("--token", required=True)
    sp.add_argument("--room-id", required=True)
    sp.add_argument("--content", required=True)
    sp.add_argument("--client-msg-id", default="")
    sp.set_defaults(func=cmd_send)

    sp = sub.add_parser("pull")
    sp.add_argument("--token", required=True)
    sp.add_argument("--room-id", required=True)
    sp.add_argument("--after-id", default=0)
    sp.add_argument("--limit", default=50)
    sp.set_defaults(func=cmd_pull)

    sp = sub.add_parser("tail")
    sp.add_argument("--token", required=True)
    sp.add_argument("--room-id", required=True)
    sp.add_argument("--after-id", default=0)
    sp.add_argument("--interval", default=1)
    sp.set_defaults(func=cmd_tail)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
