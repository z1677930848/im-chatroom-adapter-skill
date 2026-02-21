<?php

declare(strict_types=1);

require_once __DIR__ . '/db.php';
require_once __DIR__ . '/jwt.php';
require_once __DIR__ . '/http.php';

function current_user_id(): int
{
    $token = get_bearer_token();
    if (!$token) {
        json_response(401, 'unauthorized', null, 401);
    }

    $payload = verify_jwt($token);
    if (!$payload || !isset($payload['uid'])) {
        json_response(401, 'invalid token', null, 401);
    }

    return (int)$payload['uid'];
}

function ensure_conversation_member(int $conversationId, int $userId): void
{
    $pdo = db();
    $stmt = $pdo->prepare('SELECT 1 FROM conversation_members WHERE conversation_id = :cid AND user_id = :uid');
    $stmt->execute([':cid' => $conversationId, ':uid' => $userId]);
    if (!$stmt->fetchColumn()) {
        json_response(403, 'forbidden', null, 403);
    }
}

function ensure_public_room(int $userId): int
{
    $pdo = db();

    // 轻量元数据表：保存公共聊天室映射
    $pdo->exec("CREATE TABLE IF NOT EXISTS public_rooms (
        id BIGSERIAL PRIMARY KEY,
        room_key VARCHAR(50) NOT NULL UNIQUE,
        conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )");

    $stmt = $pdo->prepare("SELECT conversation_id FROM public_rooms WHERE room_key = 'global' LIMIT 1");
    $stmt->execute();
    $cid = $stmt->fetchColumn();

    if (!$cid) {
        $pdo->beginTransaction();
        try {
            // 复用 existing type，避免触发 schema.sql 中 type CHECK 约束问题
            $stmt = $pdo->prepare("INSERT INTO conversations(type) VALUES ('single') RETURNING id");
            $stmt->execute();
            $cid = (int)$stmt->fetchColumn();

            $stmt = $pdo->prepare('INSERT INTO public_rooms(room_key, conversation_id) VALUES (:rk, :cid)');
            $stmt->execute([':rk' => 'global', ':cid' => $cid]);

            $pdo->commit();
        } catch (Throwable $e) {
            $pdo->rollBack();
            throw $e;
        }
    }

    $cid = (int)$cid;

    // 确保当前用户是公共聊天室成员
    $stmt = $pdo->prepare('SELECT 1 FROM conversation_members WHERE conversation_id = :cid AND user_id = :uid');
    $stmt->execute([':cid' => $cid, ':uid' => $userId]);
    if (!$stmt->fetchColumn()) {
        $stmt = $pdo->prepare('INSERT INTO conversation_members(conversation_id, user_id) VALUES (:cid, :uid) ON CONFLICT (conversation_id, user_id) DO NOTHING');
        $stmt->execute([':cid' => $cid, ':uid' => $userId]);
    }

    return $cid;
}
