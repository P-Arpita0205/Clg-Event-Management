param(
    [Parameter(Mandatory=$true)][string]$BackupFile
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $BackupFile)) { throw "Backup file not found: $BackupFile" }
if (-not $env:MYSQL_HOST -or -not $env:MYSQL_DATABASE -or -not $env:MYSQL_USER -or -not $env:MYSQL_PASSWORD) {
    throw "Set MYSQL_HOST, MYSQL_DATABASE, MYSQL_USER, and MYSQL_PASSWORD."
}

$confirmation = Read-Host "Restore '$BackupFile' into $env:MYSQL_DATABASE? Type RESTORE"
if ($confirmation -ne "RESTORE") { throw "Restore cancelled." }

$env:MYSQL_PWD = $env:MYSQL_PASSWORD
Get-Content -Raw $BackupFile | mysql --host=$env:MYSQL_HOST --user=$env:MYSQL_USER $env:MYSQL_DATABASE
Remove-Item Env:MYSQL_PWD
Write-Output "Database restore completed."
