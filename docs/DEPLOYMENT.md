# Production deployment guide

## Scope and status

This guide prepares an application for college deployment. It is not evidence that a target environment has been deployed. Hosting credentials, domain ownership, TLS certificates, and MySQL infrastructure must be supplied by the college.

## Prerequisites

- Ubuntu LTS or Windows Server host
- Docker Engine and Docker Compose
- DNS record for the college domain
- TLS certificate and private key
- Managed or dedicated MySQL 8 database
- Reverse proxy such as Nginx
- Encrypted backup storage

## 1. Prepare secrets

Generate secrets outside source control:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set `SECRET_KEY`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`, and `SESSION_COOKIE_SECURE=true`. Do not use Docker Compose fallback passwords.

## 2. Configure MySQL

Create a dedicated database and least-privilege account:

```sql
CREATE DATABASE college_events CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'college_app'@'%' IDENTIFIED BY '<strong-password>';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES ON college_events.* TO 'college_app'@'%';
FLUSH PRIVILEGES;
```

Set:

```text
APP_ENV=production
DATABASE_URL=mysql+pymysql://college_app:<password>@<mysql-host>:3306/college_events
```

## 3. Build and start

```powershell
docker compose up --build -d
docker compose exec web flask db upgrade
docker compose exec web flask init-db
docker compose exec web flask create-admin
docker compose ps
```

Do not run `seed-demo` on a public production environment.

## 4. Configure HTTPS

Adapt [Nginx configuration](/C:/Users/user/OneDrive/Desktop/temp/college_event_management/deploy/nginx.conf.example) and install the domain certificate. Force HTTP to HTTPS, enable HSTS, and confirm the health endpoint is reachable over HTTPS.

Forward `X-Forwarded-Proto: https` and `Host` to Flask. Terminate TLS at Nginx or the hosting load balancer.

## 5. Final host checks

- `GET /health` returns HTTP 200 and database connected
- HTTP redirects to HTTPS
- Secure session cookie is set
- Uploads persist through restarts
- Database migrations finish cleanly
- Administrator login succeeds
- Browser console has no application errors
- Desktop, tablet, and mobile workflows are accepted
- Backups restore to a non-production database successfully

## 6. Rollback

1. Restore the previous application image tag.
2. Restart the web service.
3. Restore the database snapshot only if migration or data changes require it.
4. Verify `/health`, login, event listing, and administrator access.
