#!/bin/sh
# Выбор конфигурации nginx на старте контейнера (env-driven, часть entrypoint nginx:alpine).
#   WEB_TLS=true + есть сертификат  → HTTPS (:443) с редиректом и вебхуком.
#   иначе                          → HTTP (:80), обслуживает ACME-челлендж.
# Такой фолбэк снимает проблему «курица-яйцо»: ставишь WEB_TLS=true сразу, nginx поднимается
# на :80, certbot получает сертификат, перезапускаешь web — и он сам переключается на TLS.
set -eu

CERT="/etc/letsencrypt/live/${WEB_SERVER_NAME:-_}/fullchain.pem"

if [ "${WEB_TLS:-false}" = "true" ] && [ -f "$CERT" ]; then
    export WEB_SERVER_NAME
    # envsubst с ЯВНЫМ списком: подставляем только WEB_SERVER_NAME, а $host/$uri/… не трогаем.
    envsubst '${WEB_SERVER_NAME}' \
        < /etc/nginx/qc/https.conf.template > /etc/nginx/conf.d/default.conf
    echo "[qc] nginx: TLS включён (server_name=${WEB_SERVER_NAME})"
else
    cp /etc/nginx/qc/http.conf /etc/nginx/conf.d/default.conf
    if [ "${WEB_TLS:-false}" = "true" ]; then
        echo "[qc] nginx: WEB_TLS=true, но нет сертификата $CERT → пока HTTP."
        echo "[qc] Получи сертификат (certbot), затем: docker compose restart web"
    else
        echo "[qc] nginx: HTTP :80 (TLS выключен)"
    fi
fi
