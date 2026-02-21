<?php

declare(strict_types=1);

require_once __DIR__ . '/env.php';

function b64url_encode(string $data): string
{
    return rtrim(strtr(base64_encode($data), '+/', '-_'), '=');
}

function b64url_decode(string $data): string
{
    $pad = strlen($data) % 4;
    if ($pad > 0) {
        $data .= str_repeat('=', 4 - $pad);
    }
    return base64_decode(strtr($data, '-_', '+/')) ?: '';
}

function jwt_secret(): string
{
    return env('JWT_SECRET', 'please_change_this_secret') ?? 'please_change_this_secret';
}

function jwt_expire_seconds(): int
{
    return (int)(env('JWT_EXPIRE_SECONDS', '7200') ?? '7200');
}

function create_jwt(array $payload): string
{
    $header = ['alg' => 'HS256', 'typ' => 'JWT'];
    $now = time();

    $payload['iat'] = $now;
    $payload['exp'] = $now + jwt_expire_seconds();

    $h = b64url_encode(json_encode($header, JSON_UNESCAPED_UNICODE));
    $p = b64url_encode(json_encode($payload, JSON_UNESCAPED_UNICODE));
    $sig = hash_hmac('sha256', $h . '.' . $p, jwt_secret(), true);

    return $h . '.' . $p . '.' . b64url_encode($sig);
}

function verify_jwt(string $token): ?array
{
    $parts = explode('.', $token);
    if (count($parts) !== 3) {
        return null;
    }

    [$h, $p, $s] = $parts;

    $expected = b64url_encode(hash_hmac('sha256', $h . '.' . $p, jwt_secret(), true));
    if (!hash_equals($expected, $s)) {
        return null;
    }

    $payloadJson = b64url_decode($p);
    if ($payloadJson === '') {
        return null;
    }

    $payload = json_decode($payloadJson, true);
    if (!is_array($payload)) {
        return null;
    }

    if (!isset($payload['exp']) || time() > (int)$payload['exp']) {
        return null;
    }

    return $payload;
}
