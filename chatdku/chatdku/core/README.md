# ChatDKU Core Development Guide

- [ ] TODO: Add more in this section.

# About ChatDKU Syllabi Tool 
Similar to ChatDKU's other tools, the Syllabi Tool uses DSPy for orchestrating tasks for the LLM. The folder `chatdku/chatdku/core/tools/syllabi_tool` contains the code that culminates in `query_curriculum_db.py`, which is passed onto `agent.py` as a tool for the Planner to use. 

Currently, the problem in implementing this tool is the amount of latency it adds to ChatDKU's response due to the constant connecting and disconnecting from the Postgres DB. This can be solved with a proper DB connection handled by Django. 

## About the Local Document Ingestion Pipeline

This colder also contains the ingestion mechanism (`local_ingest.py`) for extracting structured data from PDF and DOCX files into a Postgres database called  `chatdku_db` under the username `chatdku_user`. 

The schema for this database can be found in `create_table.sql`. Running this SQL query inside Postgres will remove all data from the classes table, so any modifications to the schema should be made as post-hoc SQL schema definition queries. 

You may also find a file called `classes_schema.json`. This is a JSON representation of the same schema defined in the `create_table.sql` file. This file **MUST** be in-sync with the actual schema used in the database, as both the document ingestion **and** SQL generation agent use this as a reference. (this is faster than using `get_schema.py` for reading schema during runtime)
