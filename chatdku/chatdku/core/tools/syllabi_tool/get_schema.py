import psycopg2
from os import getenv


def fetch_schema(conn):
    # print("Fetching schema...")
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name = 'classes';
    """)
    tables = [row[0] for row in cur.fetchall()]
    schema = {}
    for table in tables:
        cur.execute(f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = '{table}';
        """)
        schema[table] = {col: dtype for col, dtype in cur.fetchall()}
    # print("Schema fetched!")
    # print(schema)
    return str(schema)


connection = psycopg2.connect(
    database="chatdku_db",  # Your database name
    user="chatdku_user",  # Your username
    password=getenv("DB_PWD"),  # Your password
    host="localhost",  # Host address (often "localhost")
    port="5432",  # Default PostgreSQL port
)

print(fetch_schema(connection))
