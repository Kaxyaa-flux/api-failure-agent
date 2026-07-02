import os

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL.startswith("postgres"):
    from app.db_postgres import *
else:
    from app.db_sqlite import *
