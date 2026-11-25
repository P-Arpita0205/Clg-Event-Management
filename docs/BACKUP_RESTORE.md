# Database backup and restoration

## Policy

- Use encrypted storage for every backup.
- Create an automated daily backup.
- Retain at least 7 daily, 4 weekly, and 12 monthly snapshots unless college policy requires more.
- Test restoration at least monthly on an isolated database.
- Never use a production backup for unauthorized data access.

## PowerShell backup

Set environment variables and run:

```powershell
$env:MYSQL_HOST="mysql.example.edu"
$env:MYSQL_DATABASE="college_events"
$env:MYSQL_USER="college_backup"
$env:MYSQL_PASSWORD="<backup-password>"
.\scripts\backup_mysql.ps1 -BackupDirectory "D:\CollegeBackups"
```

The backup account needs backup/read and lock privilege as authorized by the college DBA.

## PowerShell restoration

```powershell
$env:MYSQL_HOST="mysql.example.edu"
$env:MYSQL_DATABASE="college_events_restore"
$env:MYSQL_USER="college_restore"
$env:MYSQL_PASSWORD="<restore-password>"
.\scripts\restore_mysql.ps1 -BackupFile "D:\CollegeBackups\college-events-20261125-120000.sql"
```

The restore script requires the exact word `RESTORE` before proceeding.

## Linux equivalents

```sh
export MYSQL_HOST=mysql.example.edu
export MYSQL_DATABASE=college_events
export MYSQL_USER=college_backup
export MYSQL_PASSWORD='<backup-password>'
./scripts/backup_mysql.sh /var/backups/campus-connect
```

Restoration:

```sh
export MYSQL_DATABASE=college_events_restore
./scripts/restore_mysql.sh /var/backups/campus-connect/college-events-20261125-120000.sql
```

## Uploaded files

The database backup does not include uploaded posters, gallery images, or generated certificates. Back up `uploads/` and restore it with the matching database snapshot:

```text
uploads/
  certificates/
  gallery/
```

Store application uploads on persistent storage rather than inside an ephemeral container.

## Recovery validation

After restore:

1. Run `flask db current`.
2. Open `/health`.
3. Sign in as the administrator.
4. Check recent events and certificates.
5. Verify a known QR and certificate record.
6. Confirm uploaded files are readable.
