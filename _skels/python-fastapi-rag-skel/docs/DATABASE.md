# Database Configuration Guide

This guide covers database setup, configuration, and migrations for PostgreSQL and MySQL.

## Table of Contents

- [Overview](#overview)
- [PostgreSQL Setup](#postgresql-setup)
- [MySQL Setup](#mysql-setup)
- [Migrations with Alembic](#migrations-with-alembic)
- [Connection Pooling](#connection-pooling)
- [Docker Database Setup](#docker-database-setup)
- [Kubernetes Database Setup](#kubernetes-database-setup)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

## Overview

The project uses SQLAlchemy 2.0+ with async support and SQLModel for ORM. Both PostgreSQL and MySQL are supported.

### Supported Databases

| Database | Driver | URL Format |
|----------|--------|------------|
| PostgreSQL | asyncpg | `postgresql+asyncpg://user:pass@host:5432/db` |
| PostgreSQL (sync) | psycopg2 | `postgresql://user:pass@host:5432/db` |
| MySQL | asyncmy | `mysql+asyncmy://user:pass@host:3306/db` |
| MySQL (sync) | pymysql | `mysql+pymysql://user:pass@host:3306/db` |
| SQLite (testing) | aiosqlite | `sqlite+aiosqlite:///./test.db` |

## PostgreSQL Setup

### Local Installation

#### macOS (Homebrew)

```bash
# Install PostgreSQL
brew install postgresql@16

# Start service
brew services start postgresql@16

# Create database and user
createuser -s app
createdb -O app app

# Set password
psql -c "ALTER USER app PASSWORD 'your-password';"
```

#### Ubuntu/Debian

```bash
# Add PostgreSQL repo
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -

# Install
sudo apt-get update
sudo apt-get install -y postgresql-16

# Create database and user
sudo -u postgres createuser -s app
sudo -u postgres createdb -O app app
sudo -u postgres psql -c "ALTER USER app PASSWORD 'your-password';"
```

### Configuration

Update `.env`:

```bash
# Async driver (recommended)
DATABASE_URL=postgresql+asyncpg://app:your-password@localhost:5432/app

# Sync driver (for migrations)
DATABASE_SYNC_URL=postgresql://app:your-password@localhost:5432/app
```

### PostgreSQL Extensions

Common extensions to enable:

```sql
-- Connect to database
psql -U app -d app

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- Trigram similarity
CREATE EXTENSION IF NOT EXISTS "btree_gin";  -- GIN indexes
```

### Performance Tuning

Edit `postgresql.conf`:

```ini
# Memory
shared_buffers = 256MB           # 25% of RAM for dedicated server
effective_cache_size = 768MB     # 75% of RAM
work_mem = 16MB                  # Per operation memory

# Connections
max_connections = 100

# Write Ahead Log
wal_buffers = 16MB
checkpoint_completion_target = 0.9

# Query Planning
random_page_cost = 1.1           # For SSDs
effective_io_concurrency = 200   # For SSDs
```

## MySQL Setup

### Local Installation

#### macOS (Homebrew)

```bash
# Install MySQL
brew install mysql@8.0

# Start service
brew services start mysql@8.0

# Secure installation
mysql_secure_installation

# Create database and user
mysql -u root -p <<EOF
CREATE DATABASE app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'app'@'localhost' IDENTIFIED BY 'your-password';
GRANT ALL PRIVILEGES ON app.* TO 'app'@'localhost';
FLUSH PRIVILEGES;
EOF
```

#### Ubuntu/Debian

```bash
# Install
sudo apt-get update
sudo apt-get install -y mysql-server-8.0

# Secure installation
sudo mysql_secure_installation

# Create database and user
sudo mysql <<EOF
CREATE DATABASE app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'app'@'localhost' IDENTIFIED BY 'your-password';
GRANT ALL PRIVILEGES ON app.* TO 'app'@'localhost';
FLUSH PRIVILEGES;
EOF
```

### Configuration

Update `.env`:

```bash
# Async driver (recommended)
DATABASE_URL=mysql+asyncmy://app:your-password@localhost:3306/app

# Sync driver (for migrations)
DATABASE_SYNC_URL=mysql+pymysql://app:your-password@localhost:3306/app
```

### MySQL Settings

Edit `my.cnf`:

```ini
[mysqld]
# Character set
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

# InnoDB
innodb_buffer_pool_size = 256M
innodb_log_file_size = 64M
innodb_flush_log_at_trx_commit = 2

# Connections
max_connections = 100

# Query cache (MySQL 8.0 removed this)
# Use application-level caching instead
```

### Install Python Drivers

```bash
# PostgreSQL
uv pip install asyncpg psycopg2-binary

# MySQL
uv pip install asyncmy pymysql cryptography
```

## Migrations with Alembic

### Initial Setup

```bash
# Initialize Alembic (if not already done)
alembic init alembic

# Edit alembic.ini
# Set sqlalchemy.url or use env variable
```

### Configure `alembic/env.py`

```python
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Import your models
from core.adapters.sql import Base
from app.example_items.models import Item  # Import all models

config = context.config

# Set URL from environment
config.set_main_option(
    "sqlalchemy.url",
    os.getenv("DATABASE_SYNC_URL", os.getenv("DATABASE_URL", ""))
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### Common Migration Commands

```bash
# Create a new migration
alembic revision --autogenerate -m "add users table"

# Apply all migrations
alembic upgrade head

# Apply specific migration
alembic upgrade +1

# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade abc123

# View current revision
alembic current

# View migration history
alembic history

# Generate SQL without applying
alembic upgrade head --sql > migration.sql
```

### Migration Best Practices

1. **Always review auto-generated migrations** - Alembic may miss some changes
2. **Test migrations on a copy of production data**
3. **Make migrations reversible** when possible
4. **Use batch operations** for large tables:

```python
def upgrade():
    # For large tables, use batch operations
    with op.batch_alter_table('large_table') as batch_op:
        batch_op.add_column(sa.Column('new_col', sa.String(50)))
```

## Connection Pooling

### SQLAlchemy Pool Configuration

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,           # Number of persistent connections
    max_overflow=10,       # Additional connections when pool is full
    pool_timeout=30,       # Seconds to wait for connection
    pool_recycle=1800,     # Recycle connections after 30 minutes
    pool_pre_ping=True,    # Verify connection before use
)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

### Connection Pool Sizing

```
pool_size = (core_count * 2) + effective_spindle_count

For web apps:
- Development: pool_size=5, max_overflow=5
- Production: pool_size=10-20, max_overflow=20-40
```

### PgBouncer (PostgreSQL)

For high-concurrency applications, use PgBouncer:

```ini
# pgbouncer.ini
[databases]
app = host=localhost port=5432 dbname=app

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 20
```

## Docker Database Setup

### PostgreSQL Container

```bash
# Run PostgreSQL
docker run -d \
  --name postgres \
  -e POSTGRES_USER=app \
  -e POSTGRES_PASSWORD=app \
  -e POSTGRES_DB=app \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:16-alpine

# Connect
docker exec -it postgres psql -U app -d app
```

### MySQL Container

```bash
# Run MySQL
docker run -d \
  --name mysql \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=app \
  -e MYSQL_USER=app \
  -e MYSQL_PASSWORD=app \
  -p 3306:3306 \
  -v mysql_data:/var/lib/mysql \
  mysql:8.0

# Connect
docker exec -it mysql mysql -u app -papp app
```

### Docker Compose

The project's `docker-compose.yml` includes PostgreSQL:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-app}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-app}
      POSTGRES_DB: ${POSTGRES_DB:-app}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d app"]
      interval: 10s
      timeout: 5s
      retries: 5
```

To use MySQL instead, modify `docker-compose.yml`:

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-root}
      MYSQL_DATABASE: ${MYSQL_DATABASE:-app}
      MYSQL_USER: ${MYSQL_USER:-app}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD:-app}
    volumes:
      - mysql_data:/var/lib/mysql
    ports:
      - "3306:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  mysql_data:
```

## Kubernetes Database Setup

### PostgreSQL StatefulSet

See `k8s/postgres.yaml` for the full manifest. Key points:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  serviceName: postgres
  replicas: 1
  template:
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          env:
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: postgres-secrets
                  key: username
          volumeMounts:
            - name: postgres-storage
              mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
    - metadata:
        name: postgres-storage
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 10Gi
```

### Production Database Options

For production, consider managed databases:

| Provider | PostgreSQL | MySQL |
|----------|------------|-------|
| AWS | RDS, Aurora | RDS, Aurora |
| GCP | Cloud SQL | Cloud SQL |
| Azure | Azure Database | Azure Database |
| DigitalOcean | Managed Databases | Managed Databases |

### Connecting to External Database

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: database-secrets
type: Opaque
stringData:
  database-url: "postgresql+asyncpg://user:pass@rds-endpoint.amazonaws.com:5432/app"
```

## Testing

### Test Database Setup

Use SQLite for unit tests:

```python
# conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

### Integration Testing with Docker

```bash
# Start test database
docker compose up -d postgres

# Run tests
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/app pytest

# Cleanup
docker compose down -v
```

### Testcontainers

For isolated integration tests:

```python
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres.get_connection_url()
```

## Troubleshooting

### Connection Refused

```bash
# Check if database is running
docker compose ps

# Check logs
docker compose logs postgres

# Test connection
psql -h localhost -U app -d app -c "SELECT 1"
```

### Authentication Failed

```bash
# Reset password
docker compose exec postgres psql -U postgres -c "ALTER USER app PASSWORD 'newpassword';"

# Update .env
DATABASE_URL=postgresql+asyncpg://app:newpassword@localhost:5432/app
```

### Too Many Connections

```bash
# Check active connections
psql -c "SELECT count(*) FROM pg_stat_activity;"

# Kill idle connections
psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND query_start < now() - interval '5 minutes';"
```

### Slow Queries

```bash
# Enable query logging (PostgreSQL)
psql -c "ALTER SYSTEM SET log_min_duration_statement = 1000;"
psql -c "SELECT pg_reload_conf();"

# Check slow queries
tail -f /var/log/postgresql/postgresql-16-main.log
```

### Migration Issues

```bash
# Check current state
alembic current

# Show pending migrations
alembic history --indicate-current

# Force revision (use with caution)
alembic stamp head

# Generate fresh migration
alembic revision --autogenerate -m "fresh start"
```

### Data Recovery

```bash
# PostgreSQL backup
pg_dump -U app -d app > backup.sql

# PostgreSQL restore
psql -U app -d app < backup.sql

# MySQL backup
mysqldump -u app -p app > backup.sql

# MySQL restore
mysql -u app -p app < backup.sql
```

## Best Practices Summary

1. **Use async drivers** (`asyncpg`, `asyncmy`) for FastAPI
2. **Configure connection pooling** appropriately for your workload
3. **Use migrations** for all schema changes
4. **Separate sync URL** for Alembic migrations
5. **Use secrets** for credentials (never commit to git)
6. **Regular backups** with tested restore procedures
7. **Monitor connections** and query performance
8. **Use managed databases** in production when possible
