@echo off
rem Restore von Postgres + MinIO S3-Bucket aus scripts\backups\
rem Container muessen laufen (start-local.bat).
rem ACHTUNG: ueberschreibt existierende Daten.
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
if not exist "%BACKUP_DIR%\postgres.dump" (
    echo scripts\backups\postgres.dump nicht gefunden.
    exit /b 1
)
if not exist "%BACKUP_DIR%\minio" (
    echo scripts\backups\minio\ nicht gefunden.
    exit /b 1
)

echo ACHTUNG: bestehende Daten in DB %POSTGRES_DB% und Bucket %S3_BUCKET% werden ueberschrieben.
set /p CONFIRM="Weiter? (y/N) "
if /i not "%CONFIRM%"=="y" (
    echo Abgebrochen.
    exit /b 0
)

echo [1/2] Postgres-Restore aus scripts\backups\postgres.dump ...
docker cp "%BACKUP_DIR%\postgres.dump" kis-postgres:/tmp/postgres.dump
if errorlevel 1 goto :error
docker exec kis-postgres sh -c "dropdb -U %POSTGRES_USER% --if-exists %POSTGRES_DB% && createdb -U %POSTGRES_USER% %POSTGRES_DB%"
if errorlevel 1 goto :error
docker exec kis-postgres pg_restore -U %POSTGRES_USER% -d %POSTGRES_DB% --no-owner --no-privileges /tmp/postgres.dump
if errorlevel 1 goto :error
docker exec kis-postgres rm -f /tmp/postgres.dump

echo [2/2] MinIO-Bucket %S3_BUCKET% aus scripts\backups\minio\ ...
docker run --rm --network container:kis-minio -v "%BACKUP_DIR%\minio:/data" --entrypoint sh minio/mc -c "mc alias set local http://127.0.0.1:9000 %S3_ACCESS_KEY% %S3_SECRET_KEY% >/dev/null && mc mb --ignore-existing local/%S3_BUCKET% >/dev/null && mc mirror --overwrite --remove --quiet /data local/%S3_BUCKET%"
if errorlevel 1 goto :error

echo.
echo Restore fertig.
goto :eof

:error
echo.
echo Restore FEHLGESCHLAGEN.
exit /b 1
