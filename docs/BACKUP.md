# Backing up and restoring Horolog

The schema is deliberately small — three tables, plus `oauth_tokens` for
connected accounts (see [ARCHITECTURE.md](ARCHITECTURE.md#database-schema)) —
so a full backup is one command either way.

**There is no schema-migration tooling.** `init_db()` only ever creates
tables that don't exist yet; it never alters an existing one. Back up before
pulling a new version, and check [CHANGELOG.md](../CHANGELOG.md) first — an
entry there will say if a schema change needs anything beyond a normal pull.

## SQLite (the default)

The whole database is one file.

**Local development** — it's just `services/api/horolog.db`:
```bash
cp services/api/horolog.db backup-$(date +%F).db
```

**Docker** — the file lives inside the `api-data` volume. `.backup` is
SQLite's own safe-copy command, so this works without stopping the
container:
```bash
docker compose -f infra/docker-compose.yml exec api \
  sqlite3 /app/data/horolog.db ".backup /app/data/backup.db"
docker compose -f infra/docker-compose.yml cp api:/app/data/backup.db ./backup.db
```

**Restore** — stop the stack, replace the file, start it again:
```bash
docker compose -f infra/docker-compose.yml down
docker compose -f infra/docker-compose.yml cp ./backup.db api:/app/data/horolog.db
docker compose -f infra/docker-compose.yml up -d
```

## Postgres

Matches the user/database names in `infra/docker-compose.yml`.

**Backup:**
```bash
docker compose -f infra/docker-compose.yml exec db \
  pg_dump -U horolog horolog > backup.sql
```

**Restore** (into a fresh, running `db` service):
```bash
docker compose -f infra/docker-compose.yml exec -T db \
  psql -U horolog horolog < backup.sql
```
