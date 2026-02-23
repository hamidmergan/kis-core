# Local Development Notes

## Container starten

### Lokal
```bash
docker-compose up -d --build
```

### TH-Server
```bash
./start-th.sh
```

### Nginx-Server (Hetzner)
```bash
./start-nginx.sh
```

## TablePlus - DB live anschauen
DB aus Container kopieren und in TablePlus öffnen:
```bash
docker cp kis-thl-backend:/app/data/database.db C:\Users\Hamid\Documents\github-hm\kis-thl\database.db
```
Dann F5 in TablePlus zum Aktualisieren.

## Storage prüfen
```bash
docker exec kis-thl-backend find /app/storage -type f
```