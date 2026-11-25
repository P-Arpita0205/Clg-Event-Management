param(
    [Parameter(Mandatory=$true)][string]$BackupDirectory
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$file = Join-Path $BackupDirectory "college-events-$stamp.sql"

if (-not $env:MYSQL_HOST -or -not $env:MYSQL_DATABASE -or -not $env:MYSQL_USER -or -not $env:MYSQL_PASSWORD) {
    throw "Set MYSQL_HOST, MYSQL_DATABASE, MYSQL_USER, and MYSQL_PASSWORD."
}

$env:MYSQL_PWD = $env:MYSQL_PASSWORD
mysqldump --host=$env:MYSQL_HOST --user=$env:MYSQL_USER --single-transaction --routines --triggers $env:MYSQL_DATABASE > $file
Remove-Item Env:MYSQL_PWD

Write-Output "Database backup created: $file"
