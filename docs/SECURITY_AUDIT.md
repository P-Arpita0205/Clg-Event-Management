# Security audit checklist

## Implemented

- Werkzeug password hashing
- Flask-Login authenticated sessions
- Role-based route guards
- Flask-WTF CSRF protection
- Parameterized SQLAlchemy queries
- Upload size limit
- Upload extension validation
- HTTP-only session cookies
- Secure-cookie production setting
- X-Content-Type-Options header
- X-Frame-Options header
- Referrer-Policy header
- HSTS production setting
- Custom 403, 404, 413, and 500 pages
- Database rollback on server-error handling
- Environment-based secrets

## Target deployment requirements

- Replace every fallback password and secret.
- Store secrets in the platform secret manager or restricted environment file.
- Restrict MySQL network access to application hosts.
- Run TLS 1.2 or newer.
- Rotate database credentials and session secrets on compromise.
- Enable backup encryption and restore testing.
- Review application logs without exposing passwords or secrets.
- Apply OS, container, Python, and database security updates.
- Test uploads for file-type and size abuse.
- Confirm every role cannot access protected routes.
- Rate-limit login and public verification routes at the reverse proxy or hosting layer.
- Configure CSP only after testing every external CDN and inline script.
