import dspy
from sql_agent import StepByStepSQLModule
import psycopg2

# import getpass
from os import getenv
import re


def remove_think_section(text: str) -> str:
    """
    Removes the first <think>...</think> section (including the tags) from the string.
    Works across multiple lines.
    """
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)


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


try:
    # db_password = getpass.getpass("Enter database password: ")

    # Establish the connection
    connection = psycopg2.connect(
        database="chatdku_db",  # Your database name
        user="chatdku_user",  # Your username
        password=getenv("DB_PWD"),  # Your password
        host="localhost",  # Host address (often "localhost")
        port="5432",  # Default PostgreSQL port
    )

    cursor = connection.cursor()

    cursor.execute("SELECT version();")
    record = cursor.fetchone()
    print("You are connected to -", record)

    # lm = dspy.LM("ollama_chat/qwen3:4b", api_base="http://localhost:11434", api_key="")
    new_lm = dspy.OpenAI(
        model="Qwen/Qwen3-8B",
        api_base="http://127.0.0.1:18082/v1/",
        api_key="dummy",
        model_type="chat",
        max_tokens=40960,
        stop=["<|im_end|>"],
    )
    dspy.configure(lm=new_lm)
    sql_agent = StepByStepSQLModule()
    print("Executing agent...")

    while True:
        user_q = str(input("Question: "))
        final_sql = sql_agent(question=user_q, db_schema=fetch_schema(conn=connection))
        print("\033[34mFinal SQL:", final_sql, "\033[0m")
        try:
            cursor.execute(final_sql)
            tool_out = str(cursor.fetchall())
        except Exception as e:
            print("Improper query:", e)
            tool_out = str(e)
        print(
            "\033[32m",
            remove_think_section(
                dspy.Predict("question, tool_output -> comprehensive_natural_answer")(
                    question=user_q, tool_output=tool_out
                ).comprehensive_natural_answer
            ),
            "\033[0m",
        )


except Exception as e:
    print("Exception while testing: ", e)

finally:
    print("Closing DB connection...")
    if "cursor" in locals():
        cursor.close()
    if "connection" in locals() and connection:
        connection.close()
        print("PostgreSQL connection is closed")
