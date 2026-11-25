#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /backup/file.sql" >&2
  exit 1
fi

: "${MYSQL_HOST:?MYSQL_HOST is required}"
: "${MYSQL_DATABASE:?MYSQL_DATABASE is required}"
: "${MYSQL_USER:?MYSQL_USER is required}"
: "${MYSQL_PASSWORD:?MYSQL_PASSWORD is required}"

printf "Restore '%s' into %s? Type RESTORE: " "$1" "$MYSQL_DATABASE"
read -r confirmation
if [ "$confirmation" != "RESTORE" ]; then
  echo "Restore cancelled."
  exit 1
fi

MYSQL_PWD="$MYSQL_PASSWORD" mysql \
  --host="$MYSQL_HOST" --user="$MYSQL_USER" "$MYSQL_DATABASE" < "$1"
echo "Database restore completed."
