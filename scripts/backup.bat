@echo off
rem Backup von Postgres + MinIO S3-Bucket nach scripts\backups\
rem Container muessen laufen (start-local.bat).
rem Nur fuer lokale Entwicklung; wird vor Open-Source-Release entfernt.

setlocal

for /f "usebackq tokens=1,2 delims==" %%A in ("%~dp0..\.env") do (
    if /i "%%A"=="POSTGRES_USER" set POSTGRES_USER=%%B
    if /i "%%A"=="POSTGRES_DB"   set POSTGRES_DB=%%B
    if /i "%%A"=="S3_ACCESS_KEY" set S3_ACCESS_KEY=%%B
    if /i "%%A"=="S3_SECRET_KEY" set S3_SECRET_KEY=%%B
    if /i "%%A"=="S3_BUCKET"     set S3_BUCKET=%%B
)

set BACKUP_DIR=%~dp0backups
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
if not exist "%BACKUP_DIR%\minio" mkdir "%BACKUP_DIR%\minio"

echo [1/2] Postgres-Dump nach scripts\backups\postgres.dump ...
docker exec kis-postgres pg_dump -U %POSTGRES_USER% -d %POSTGRES_DB% -Fc -f /tmp/postgres.dump
if errorlevel 1 goto :error
docker cp kis-postgres:/tmp/postgres.dump "%BACKUP_DIR%\postgres.dump"
if errorlevel 1 goto :error
docker exec kis-postgres rm -f /tmp/postgres.dump

echo [2/2] MinIO-Bucket %S3_BUCKET% nach scripts\backups\minio\ ...
docker run --rm --network container:kis-minio -v "%BACKUP_DIR%\minio:/data" --entrypoint sh minio/mc -c "mc alias set local http://127.0.0.1:9000 %S3_ACCESS_KEY% %S3_SECRET_KEY% >/dev/null && mc mirror --overwrite --remove --quiet local/%S3_BUCKET% /data"
if errorlevel 1 goto :error

echo.
echo Backup fertig: %BACKUP_DIR%
goto :eof

:error
echo.
echo Backup FEHLGESCHLAGEN. Laeuft der Docker-Stack? (start-local.bat)
exit /b 1
