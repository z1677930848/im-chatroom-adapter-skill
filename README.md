# im-chatroom-adapter-skill

OpenClaw Skill for adapting a public IM chatroom system.

## Includes
- `SKILL.md`
- `references/register-tutorial.md`
- `references/api-checklist.md`
- `scripts/chatroom_client.py` (register/login/send/pull/tail)

## Quick examples
```bash
python3 scripts/chatroom_client.py --base-url http://127.0.0.1:18080 login --username demo --password '12345678'
python3 scripts/chatroom_client.py --base-url http://127.0.0.1:18080 tail --token <TOKEN> --room-id <ROOM_ID> --interval 1
```
