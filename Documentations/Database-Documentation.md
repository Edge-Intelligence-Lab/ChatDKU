# **WIP**: Database Documentation

## Introduction

We are using:
- Redis for storing text documents.
- ChromaDB for storing vector embeddings.

## Running the database

### ChromaDB
```bash
sudo docker run -d \
  --name chromadb \
  -v /datapool/db_chat_dku_advising/chroma-data:/data \
  -v /datapool/db_chat_dku_advising/config.yaml:/config.yaml \
  -p 12400:8000 \
  chromadb/chroma
```
---
- **Last Updated**: 2026-01-30
- **Version**: 1.0.0 
- **Maintainers**: Temuulen  
- **Contact**: te100@duke.edu
