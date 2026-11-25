#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /backup/directory" >&2
  exit 1
fi

: "${MYSQL_HOST:?MYSQL_HOST is required}"
: "${MYSQL_DATABASE:?MYSQL_DATABASE is required}"
: "${MYSQL_USER:?MYSQL_USER is required}"
: "${MYSQL_PASSWORD:?MYSQL_PASSWORD is required}"

mkdir -p "$1"
stamp=$(date +"%Y%m%d-%H%M%S")
file="$1/college-events-$stamp.sql"
MYSQL_PWD="$MYSQL_PASSWORD" mysqldump \
  --host="$MYSQL_HOST" --user="$MYSQL_USER" \
  --single-transaction --routines --triggers "$MYSQL_DATABASE" > "$file"
echo "Database backup created: $file"
