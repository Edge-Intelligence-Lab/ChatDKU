import dspy
import re
from pydantic import Field
from typing import Annotated, Any
from chatdku.core.tools.syllabi_tool.sql_agent import GenerateSQL
import psycopg2

# import getpass
from os import getenv


def remove_think_section(text: str) -> str:
    """
    Removes the first <think>...</think> section (including the tags) from the string.
    Works across multiple lines.
    """
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)


def fetch_schema(conn):
    # print("Fetching schema...")
    cur = conn.cursor()
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name = 'classes';
    """
    )
    tables = [row[0] for row in cur.fetchall()]
    schema = {}
    for table in tables:
        cur.execute(
            f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = '{table}';
        """
        )
        schema[table] = {col: dtype for col, dtype in cur.fetchall()}
    # print("Schema fetched!")
    # print(schema)
    return str(schema)


class QueryCurriculumDB(dspy.Module):
    """Use SQL to query anything about DKU courses classes or instructors -> natural language answer from db"""

    def __init__(
        self,
    ):
        # Establish the connection
        self.connection = psycopg2.connect(
            database="chatdku_db",  # Your database name
            user="chatdku_user",  # Your username
            password=getenv("DB_PWD"),  # Your password
            host="localhost",  # Host address (often "localhost")
            port="5432",  # Default PostgreSQL port
        )

        self.cursor = self.connection.cursor()

    def forward(
        self,
        query: Annotated[
            str,
            Field(
                description="A natural language question to ask a relational database of class and course data using SQL."
            ),
        ],
        internal_memory: dict,
        files: list,
        user_id: str = "Chat_DKU",
        search_mode: int = 0,
    ):
        try:
            self.cursor.execute("SELECT version();")
            record = self.cursor.fetchone()
            print("You are connected to -", record)

            # lm = dspy.LM("ollama_chat/qwen3:4b", api_base="http://localhost:11434", api_key="")
            # new_lm = dspy.OpenAI(
            #     model="Qwen/Qwen3-8B",
            #     api_base="http://127.0.0.1:18085/v1/",
            #     api_key="dummy",
            #     model_type="chat",
            #     max_tokens=40960,
            #     stop=["<|im_end|>"],
            # )
            # dspy.configure(lm=new_lm)
            sql_agent = GenerateSQL()
            print("Executing agent...")

            final_sql = sql_agent(
                query=query, db_schema=fetch_schema(conn=self.connection)
            )
            print("\033[34mFinal SQL:", final_sql, "\033[0m")
            try:
                self.cursor.execute(final_sql)
                tool_out = str(self.cursor.fetchall())
            except Exception as e:
                print("Improper query:", e)
                tool_out = str(e)
            res = dspy.Predict("question, tool_output -> result, internal_result")(
                question=query, tool_output=tool_out
            )
            res.result = remove_think_section(res.result)
            res.internal_result = {res.internal_result}
            print(res)
            return res

        except Exception as e:
            print("Exception while testing: ", e)

        finally:
            print("Closing DB connection...")
            if "cursor" in locals():
                self.cursor.close()
            if "connection" in locals() and self.connection:
                self.connection.close()
                print("PostgreSQL connection is closed")
