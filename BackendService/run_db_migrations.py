import subprocess
import os

def run_alembic_upgrade():
    """Runs alembic upgrade head to migrate the DB."""
    try:
        # Environment variable for alembic
        env = os.environ.copy()
        if "DATABASE_URL" in env:
            env["DB_URL"] = env["DATABASE_URL"]
        subprocess.run(["alembic", "upgrade", "head"], check=True, env=env)
        print("Alembic migrations applied successfully.")
    except Exception as ex:
        print(f"Error running Alembic migrations: {ex}")

if __name__ == "__main__":
    run_alembic_upgrade()
