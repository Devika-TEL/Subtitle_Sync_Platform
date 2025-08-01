# Database Migration & Initialization Guide

## Requirements

- Ensure `alembic`, `psycopg2-binary`, and `sqlalchemy` are installed (see `requirements.txt`).

## Quick Start

1. **Configure DATABASE_URL**
   - Set `DATABASE_URL` in your environment or `.env` file. It should include credentials, host, and database name.
   - Example:
     ```
     DATABASE_URL=postgresql://user:password@host:5432/mydatabase
     ```

2. **Alembic Initialization**
   - On first setup, run (from BackendService directory):
     ```
     alembic init alembic
     ```
   - Edit `alembic.ini`: set `sqlalchemy.url` to your `DATABASE_URL` or (recommended) configure with the environment variable.
     Alternatively, edit `alembic/env.py`:
     ```python
     import os
     from sqlalchemy import engine_from_config
     # ...
     config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))
     ```

3. **Generate Migration**
   - To auto-generate the initial migration based on models in `database.py`:
     ```
     alembic revision --autogenerate -m "initial"
     ```

4. **Apply Migrations (Create Tables)**
   - To apply latest migrations to the DB:
     ```
     alembic upgrade head
     ```

## Development Iteration

- When models/schema change, repeat autogenerate:
  ```
  alembic revision --autogenerate -m "describe_change"
  alembic upgrade head
  ```

## Troubleshooting

- If you get connection errors, check `DATABASE_URL`, network/credentials, and Postgres instance.
- For "Target database is not up to date", rerun `alembic upgrade head`.

## Additional Notes

- **NEVER** edit the alembic `versions` manually.
- Keep models and migrations in sync.

-------
For questions, see official [Alembic Docs](https://alembic.sqlalchemy.org/en/latest/).

