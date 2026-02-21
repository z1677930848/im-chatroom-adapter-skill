<?php

declare(strict_types=1);

function env(string $key, ?string $default = null): ?string
{
    static $loaded = false;
    static $vars = [];

    if (!$loaded) {
        $path = __DIR__ . '/../.env';
        if (!file_exists($path)) {
            $path = __DIR__ . '/../.env.example';
        }

        if (file_exists($path)) {
            $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [];
            foreach ($lines as $line) {
                $line = trim($line);
                if ($line === '' || str_starts_with($line, '#')) {
                    continue;
                }
                [$k, $v] = array_pad(explode('=', $line, 2), 2, '');
                $vars[trim($k)] = trim($v);
            }
        }

        $loaded = true;
    }

    return $_ENV[$key] ?? $_SERVER[$key] ?? $vars[$key] ?? $default;
}
