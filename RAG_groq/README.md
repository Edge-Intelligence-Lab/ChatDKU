# Introduction
Use Phidata + GROQ + Streamlit to quickly build an AI Retrieval-Augmented Generation (RAG) system that can read PDFs, websites, and images for Q&A.

AI applications are advancing incredibly fast, and now it's so easy to set up a RAG system that's more advanced than many chatbots with more functionalities.

Phidata adds memory, knowledge, and tools to LLMs.

This RAG system supports databases, memory knowledge bases, and tools...

## Download Project and Initial Configuration
In your VPS or local development environment, enter the following code:

```
cd cookbook/llms/groq/rag
```

## The following 2 lines create a virtual environment (optional, suitable for Linux systems)
```
python -m venv phidata
source phidata/bin/activate
```
```
pip install -r requirements.txt
export GROQ_API_KEY=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
export OPENAI_API_KEY=<Your OpenAI API Key>
```
## Set Up Database

Use 'docker run' to install the database used by RAG:

```
docker run -d \
  -e POSTGRES_DB=ai \
  -e POSTGRES_USER=ai \
  -e POSTGRES_PASSWORD=ai \
  -e PGDATA=/var/lib/postgresql/data/pgdata \
  -v pgvolume:/var/lib/postgresql/data \
  -p 5532:5432 \
  --name pgvector \
  phidata/pgvector:16
```

After running, you can check the status with 'docker ps'.

## Run the Program
```
streamlit run app.py
```