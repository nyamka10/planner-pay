#!/bin/bash
# Первичный выпуск SSL-сертификата Let's Encrypt для planner-pay.it.ru.
# Запускать ОДИН раз на сервере, где домен planner-pay.it.ru указывает на этот хост.
# Дальнейшее продление — автоматически контейнером certbot.
set -e

domains=(planner-pay.it.ru)
email="ppankin@it.ru"
rsa_key_size=4096
data_path="./certbot"
staging=0   # 1 — тестовый сертификат Let's Encrypt (не упереться в лимиты при отладке)

if ! docker compose version >/dev/null 2>&1; then
  echo "Ошибка: нужен docker compose v2." >&2
  exit 1
fi

if [ -d "$data_path/conf/live/$domains" ]; then
  read -p "Сертификат для $domains уже есть. Перевыпустить и заменить? (y/N) " decision
  if [ "$decision" != "Y" ] && [ "$decision" != "y" ]; then
    exit
  fi
fi

if [ ! -e "$data_path/conf/options-ssl-nginx.conf" ] || [ ! -e "$data_path/conf/ssl-dhparams.pem" ]; then
  echo "### Скачиваю рекомендуемые TLS-параметры ..."
  mkdir -p "$data_path/conf"
  curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > "$data_path/conf/options-ssl-nginx.conf"
  curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem > "$data_path/conf/ssl-dhparams.pem"
fi

echo "### Создаю временный самоподписанный сертификат для $domains ..."
path="/etc/letsencrypt/live/$domains"
mkdir -p "$data_path/conf/live/$domains"
docker compose run --rm --entrypoint "\
  openssl req -x509 -nodes -newkey rsa:$rsa_key_size -days 1 \
    -keyout '$path/privkey.pem' \
    -out '$path/fullchain.pem' \
    -subj '/CN=localhost'" certbot

echo "### Запускаю nginx ..."
docker compose up --force-recreate -d nginx

echo "### Удаляю временный сертификат ..."
docker compose run --rm --entrypoint "\
  rm -Rf /etc/letsencrypt/live/$domains && \
  rm -Rf /etc/letsencrypt/archive/$domains && \
  rm -Rf /etc/letsencrypt/renewal/$domains.conf" certbot

echo "### Запрашиваю настоящий сертификат Let's Encrypt ..."
domain_args=""
for domain in "${domains[@]}"; do
  domain_args="$domain_args -d $domain"
done

case "$email" in
  "") email_arg="--register-unsafely-without-email" ;;
  *) email_arg="--email $email" ;;
esac

staging_arg=""
if [ "$staging" != "0" ]; then staging_arg="--staging"; fi

docker compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    $staging_arg \
    $email_arg \
    $domain_args \
    --rsa-key-size $rsa_key_size \
    --agree-tos \
    --no-eff-email \
    --force-renewal" certbot

echo "### Перезагружаю nginx ..."
docker compose exec nginx nginx -s reload

echo "### Готово. Откройте https://${domains[0]}"
