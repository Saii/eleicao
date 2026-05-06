# Exporta dump do banco local (data-only) para importar no Supabase.
# Uso:
#   $env:PGPASSWORD = "<sua-senha-postgres-local>"
#   .\scripts\export_dump.ps1
#
# Ou:
#   .\scripts\export_dump.ps1 -PgPassword "<senha>" -DbName campanha_ac

param(
    [string]$PgPassword,
    [string]$DbName = "campanha_ac",
    [string]$Host = "localhost",
    [string]$User = "postgres"
)

if ($PgPassword) { $env:PGPASSWORD = $PgPassword }
if (-not $env:PGPASSWORD) {
    Write-Error "Defina PGPASSWORD via env var ou parâmetro -PgPassword."
    exit 1
}

$pgdump = "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe"
if (-not (Test-Path $pgdump)) {
    Write-Error "pg_dump.exe não encontrado em $pgdump"
    exit 1
}

$out = "$PSScriptRoot\..\dump_data.sql"
& $pgdump --data-only --no-owner --no-acl --no-privileges --disable-triggers `
    -h $Host -U $User $DbName > $out

if ($LASTEXITCODE -eq 0) {
    $size = (Get-Item $out).Length / 1MB
    Write-Host "Dump gerado: $out ($([math]::Round($size,1)) MB)"
} else {
    Write-Error "Falha no pg_dump (exit $LASTEXITCODE)"
}
