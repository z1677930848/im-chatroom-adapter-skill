<?php

declare(strict_types=1);

require_once __DIR__ . '/../src/http.php';
require_once __DIR__ . '/../src/db.php';
require_once __DIR__ . '/../src/jwt.php';
require_once __DIR__ . '/../src/auth_middleware.php';

header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

$method = $_SERVER['REQUEST_METHOD'];
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH) ?: '/';

try {
    // 健康检查
    if ($method === 'GET' && $path === '/api/v1/health') {
        json_response(0, 'ok', ['service' => 'im-php-pg']);
    }

    // 普通注册入口已关闭：仅允许通过 skill 专用注册接口
    if ($method === 'POST' && $path === '/api/v1/auth/register') {
        json_response(403, 'registration via skill only', null, 403);
    }

    // skill 专用注册接口
    if ($method === 'POST' && $path === '/api/v1/skills/register') {
        $data = get_json_body();
        require_fields($data, ['username', 'password', 'nickname', 'skill_key']);

        $username = trim((string)$data['username']);
        $password = (string)$data['password'];
        $nickname = trim((string)$data['nickname']);
        $skillKey = trim((string)$data['skill_key']);

        $expected = env('SKILL_REGISTER_KEY', 'im-skill-2026');
        if ($skillKey === '' || !hash_equals($expected, $skillKey)) {
            json_response(403, 'invalid skill key', null, 403);
        }

        if (strlen($username) < 3 || strlen($username) > 50) {
            json_response(422, 'username length must be 3-50', null, 422);
        }
        if (strlen($password) < 8) {
            json_response(422, 'password must be at least 8 chars', null, 422);
        }

        $pdo = db();
        $stmt = $pdo->prepare('SELECT id FROM users WHERE username = :username LIMIT 1');
        $stmt->execute([':username' => $username]);
        if ($stmt->fetchColumn()) {
            json_response(409, 'username already exists', null, 409);
        }

        $hash = password_hash($password, PASSWORD_BCRYPT);
        $stmt = $pdo->prepare('INSERT INTO users(username, password_hash, nickname) VALUES (:username, :hash, :nickname) RETURNING id');
        $stmt->execute([
            ':username' => $username,
            ':hash' => $hash,
            ':nickname' => $nickname,
        ]);
        $uid = (int)$stmt->fetchColumn();

        json_response(0, 'ok', ['user_id' => $uid]);
    }

    // 登录
    if ($method === 'POST' && $path === '/api/v1/auth/login') {
        $data = get_json_body();
        require_fields($data, ['username', 'password']);

        $username = trim((string)$data['username']);
        $password = (string)$data['password'];

        $pdo = db();
        $stmt = $pdo->prepare('SELECT id, password_hash, nickname FROM users WHERE username = :username LIMIT 1');
        $stmt->execute([':username' => $username]);
        $user = $stmt->fetch();

        if (!$user || !password_verify($password, (string)$user['password_hash'])) {
            json_response(401, 'invalid credentials', null, 401);
        }

        $token = create_jwt(['uid' => (int)$user['id'], 'username' => $username]);

        json_response(0, 'ok', [
            'token' => $token,
            'expires_in' => jwt_expire_seconds(),
            'user' => [
                'id' => (int)$user['id'],
                'username' => $username,
                'nickname' => (string)$user['nickname'],
            ],
        ]);
    }

    // 私聊功能已关闭
    if ($method === 'POST' && $path === '/api/v1/conversations/single') {
        json_response(403, 'private chat disabled', null, 403);
    }

    // 加入公共聊天室
    if ($method === 'POST' && $path === '/api/v1/rooms/public/join') {
        $uid = current_user_id();
        $cid = ensure_public_room($uid);
        json_response(0, 'ok', [
            'room_id' => $cid,
            'room_name' => '公共聊天室',
        ]);
    }

    // 会话列表（当前仅公共聊天室）
    if ($method === 'GET' && $path === '/api/v1/conversations/list') {
        $uid = current_user_id();
        $pdo = db();

        $sql = "
        SELECT
            c.id AS conversation_id,
            '公共聊天室' AS peer_nickname,
            'public_room' AS peer_username,
            lm.id AS last_message_id,
            lm.content AS last_message_content,
            lm.created_at AS last_message_time,
            (
                SELECT COUNT(*)
                FROM messages m
                JOIN conversation_members cmx ON cmx.conversation_id = c.id AND cmx.user_id = :uid2
                WHERE m.conversation_id = c.id
                  AND m.id > COALESCE(cmx.last_read_message_id, 0)
                  AND m.sender_id <> :uid3
                  AND m.deleted_at IS NULL
            ) AS unread_count
        FROM conversations c
        JOIN conversation_members cm ON cm.conversation_id = c.id AND cm.user_id = :uid
        LEFT JOIN LATERAL (
            SELECT id, content, created_at
            FROM messages
            WHERE conversation_id = c.id AND deleted_at IS NULL
            ORDER BY id DESC
            LIMIT 1
        ) lm ON true
        ORDER BY lm.id DESC NULLS LAST, c.id DESC
        ";

        $stmt = $pdo->prepare($sql);
        $stmt->execute([
            ':uid' => $uid,
            ':uid2' => $uid,
            ':uid3' => $uid,
        ]);

        json_response(0, 'ok', ['list' => $stmt->fetchAll()]);
    }

    // 发送消息
    if ($method === 'POST' && $path === '/api/v1/messages/send') {
        $uid = current_user_id();
        $data = get_json_body();
        require_fields($data, ['conversation_id', 'content', 'client_msg_id']);

        $conversationId = (int)$data['conversation_id'];
        $content = trim((string)$data['content']);
        $clientMsgId = trim((string)$data['client_msg_id']);

        if ($conversationId <= 0) {
            json_response(422, 'invalid conversation_id', null, 422);
        }
        if ($content === '') {
            json_response(422, 'content is empty', null, 422);
        }
        if (strlen($content) > 5000) {
            json_response(422, 'content too long', null, 422);
        }
        if ($clientMsgId === '' || strlen($clientMsgId) > 64) {
            json_response(422, 'invalid client_msg_id', null, 422);
        }

        ensure_conversation_member($conversationId, $uid);

        $pdo = db();
        try {
            $stmt = $pdo->prepare('INSERT INTO messages(conversation_id, sender_id, content, content_type, client_msg_id) VALUES (:cid, :uid, :content, :ctype, :cmid) RETURNING id, created_at');
            $stmt->execute([
                ':cid' => $conversationId,
                ':uid' => $uid,
                ':content' => $content,
                ':ctype' => 'text',
                ':cmid' => $clientMsgId,
            ]);
            $msg = $stmt->fetch();

            json_response(0, 'ok', [
                'message_id' => (int)$msg['id'],
                'created_at' => $msg['created_at'],
            ]);
        } catch (PDOException $e) {
            if (str_contains($e->getMessage(), 'messages_conversation_id_client_msg_id_key')) {
                $stmt = $pdo->prepare('SELECT id, created_at FROM messages WHERE conversation_id = :cid AND client_msg_id = :cmid LIMIT 1');
                $stmt->execute([':cid' => $conversationId, ':cmid' => $clientMsgId]);
                $msg = $stmt->fetch();
                json_response(0, 'ok', [
                    'message_id' => (int)$msg['id'],
                    'created_at' => $msg['created_at'],
                    'deduplicated' => true,
                ]);
            }
            throw $e;
        }
    }

    // 拉取消息（增量）
    if ($method === 'GET' && $path === '/api/v1/messages/pull') {
        $uid = current_user_id();

        $conversationId = isset($_GET['conversation_id']) ? (int)$_GET['conversation_id'] : 0;
        $afterMessageId = isset($_GET['after_message_id']) ? (int)$_GET['after_message_id'] : 0;
        $limit = isset($_GET['limit']) ? (int)$_GET['limit'] : 50;
        $limit = max(1, min($limit, 100));

        if ($conversationId <= 0) {
            json_response(422, 'invalid conversation_id', null, 422);
        }

        ensure_conversation_member($conversationId, $uid);

        $pdo = db();
        $stmt = $pdo->prepare('SELECT m.id, m.conversation_id, m.sender_id, u.username AS sender_username, u.nickname AS sender_nickname, m.content, m.content_type, m.client_msg_id, m.created_at FROM messages m JOIN users u ON u.id = m.sender_id WHERE m.conversation_id = :cid AND m.id > :after AND m.deleted_at IS NULL ORDER BY m.id ASC LIMIT :limit');
        $stmt->bindValue(':cid', $conversationId, PDO::PARAM_INT);
        $stmt->bindValue(':after', $afterMessageId, PDO::PARAM_INT);
        $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
        $stmt->execute();
        $list = $stmt->fetchAll();

        json_response(0, 'ok', [
            'list' => $list,
            'has_more' => count($list) === $limit,
        ]);
    }

    // 标记已读
    if ($method === 'POST' && $path === '/api/v1/messages/read') {
        $uid = current_user_id();
        $data = get_json_body();
        require_fields($data, ['conversation_id', 'last_read_message_id']);

        $conversationId = (int)$data['conversation_id'];
        $lastReadMessageId = (int)$data['last_read_message_id'];

        ensure_conversation_member($conversationId, $uid);

        $pdo = db();
        $stmt = $pdo->prepare('UPDATE conversation_members SET last_read_message_id = GREATEST(COALESCE(last_read_message_id, 0), :mid) WHERE conversation_id = :cid AND user_id = :uid');
        $stmt->execute([
            ':mid' => $lastReadMessageId,
            ':cid' => $conversationId,
            ':uid' => $uid,
        ]);

        json_response(0, 'ok', ['updated' => true]);
    }

    json_response(404, 'not found', null, 404);
} catch (Throwable $e) {
    json_response(500, 'internal error', ['error' => $e->getMessage()], 500);
}
