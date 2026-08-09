import sys
import os

# Ensure root folder is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from sqlalchemy import text
from src.database.db_connection import get_db_engine

def deploy_sql_views():
    """Reads views.sql and deploys reporting views into PostgreSQL."""
    engine = get_db_engine()
    views_path = os.path.join(os.path.dirname(__file__), 'views.sql')

    if not os.path.exists(views_path):
        print(f"❌ Error: {views_path} not found.")
        return

    print("🛠️ Deploying SQL Reporting Views into PostgreSQL...")
    with open(views_path, 'r') as f:
        sql_script = f.read()

    # Execute SQL script statements
    with engine.begin() as conn:
        conn.execute(text(sql_script))

    print("🎉 All 5 SQL Reporting Views deployed successfully!")

if __name__ == "__main__":
    deploy_sql_views()