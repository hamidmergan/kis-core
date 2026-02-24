# Local Development Notes

## Container starten

### Lokal
```bash
docker-compose --profile ldap up -d --build
```

### TH-Server
```bash
./start-th.sh
```

### Hetzner/Nginx-Server
```bash
./start-nginx.sh
```

## LDAP User verwalten

### User hinzufügen oder ändern
1. `ldap/seed.ldif` anpassen (neuen User eintragen)
2. Dann einmalig ausführen:
```bash
docker cp ldap/seed.ldif kis-thl-openldap:/tmp/seed.ldif
docker exec kis-thl-openldap ldapadd -x -D "cn=admin,dc=th-luebeck,dc=de" -w admin -f /tmp/seed.ldif
```

### LDAP testen
```bash
docker exec kis-thl-backend python -c "from src.ldap_auth import authenticate_user; print(authenticate_user('hmueller', 'test123'))"
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
