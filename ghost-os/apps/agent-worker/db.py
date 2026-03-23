import os
import psycopg2
from urllib.parse import urlparse

def get_session_cookies():
    """Fetch the latest active LinkedIn session cookies from the Postgres database."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[DB] DATABASE_URL not set.")
        return None

    try:
        # Connect to Postgres
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # Query the latest active session from Prisma's UserSession table
        cur.execute('SELECT "linkedinCookie", "linkedinCsrf" FROM "UserSession" WHERE "isActive" = true ORDER BY "createdAt" DESC LIMIT 1')
        row = cur.fetchone()

        cur.close()
        conn.close()

        if row and row[0] and row[1]:
            return {
                "li_at": row[0],
                "JSESSIONID": row[1]
            }
        return None
    except Exception as e:
        print(f"[DB] Error fetching cookies from Postgres: {e}")
        return None
