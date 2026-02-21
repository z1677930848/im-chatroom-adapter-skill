FROM php:8.2-fpm-alpine

RUN set -eux; \
    apk add --no-cache $PHPIZE_DEPS postgresql-dev; \
    docker-php-ext-install pdo pdo_pgsql; \
    apk del $PHPIZE_DEPS

WORKDIR /var/www/html
