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
  -p 12400:8010 \
  chromadb/chroma \
  chroma run --host 0.0.0.0 --port 8010 --path /data
```

### Redis

When starting redis, there are two cases to consider:
#### Redis was not set up before
```bash
sudo docker run -d \
    --name redis-stack-server \
    -p 127.0.0.1:6379:6379 \
    -v /datapool/redis_data:/data \
    -e REDIS_ARGS="--requirepass <password>" \
    redis/redis-stack-server:latest
```

To test that authentication is working, run
```docker exec -it redis-stack-server redis-cli```
Then run
```PING```
If you see ```PONG```, authentication is not set up. But if you see error, run:
```bash
 AUTH <password>
```
This will give you `OK` response. Again, run: ```PING```
You should see ```PONG```

#### Redis was set up before
To start redis, run

```bash
sudo docker start redis-stack-server
```
To check whether redis is running or not, you can use
```bash
sudo docker ps | grep redis
```

#### Password
Use a strong Redis password in your `.env` file and keep it out of version control.

> [!IMPORTANT]
> When developing:
> Make sure your `.env` file has the password and host configured.
---
- **Last Updated**: 2026-01-30
- **Version**: 1.0.0 
- **Maintainers**: Temuulen  
- **Contact**: te100@duke.edu
