import psycopg2
import dspy
from .sql_agent import SQLAgent
import os
from dotenv import load_dotenv
from chatdku.chatdku.config import config


load_dotenv()

# configure LM first

lm = dspy.LM(
    model="openai/" + config.backup_llm,
    api_base=config.backup_llm_url,
    api_key=config.llm_api_key,
    model_type="chat",
    max_tokens=config.context_window,
    temperature=config.llm_temperature,
)
dspy.configure(lm=lm)

# conn = psycopg2.connect(
#     database="chatdku_db",
#     user="chatdku_user",
#     password=os.getenv("DB_PWD"),
#     host="localhost",
#     port="5432",
# )

conn = psycopg2.connect(config.psql_uri)

agent = SQLAgent(conn)

question = "Which course does prof. bing luo teach and when is the meeting time? Which session does he teach?"

result = agent(question)

print("SQL:", result["sql"])
print("Answer:", result["answer"])
print("Rows:", result["raw_rows"])
# print("Error:", result["error"])