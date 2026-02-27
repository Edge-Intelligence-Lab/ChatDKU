# Embedding Server Documentation

## Introduction

We are using [text-embedding-inference](https://github.com/huggingface/text-embedding-inference) library to embed.

From what I understand, we are using nginx to have a one port (18080) that can serve multiple models.

## Valid paths

- Embedding endpoints:
    - `/BAAI/bge-large-en-v1.5/embed`: Serves the bge-large-en-v1.5 model
    - `/BAAI/bge-m3/embed`: Serves the bge-m3 model
    - `/BAAI/bge-small-en-v1.5/embed`: Serves the bge-small-large-en-v1.5 model

- Prometheus metrics endpoints:
    - `/BAAI/bge-large-en-v1.5/metrics`: Serves the metrics endpoint for bge-large-en-v1.5
    - `/BAAI/bge-m3/metrics`: Serves the metrics endpoint for bge-m3
    - `/BAAI/bge-small-en-v1.5/metrics`: Serves the metrics endpoint for bge-small-large-en-v1.5

## Usage

Just run any of the scripts in the `datapool/tei` directory.
For example:

```bash
sudo sh ./start_large_m3.sh
```

## Key Configuration Files
```
/datapool/tei/
├── nginx.conf                 # Nginx configuration
├── start_large_m3.sh          # Script to start bge large m3 server
├── start_m3.sh                # Script to start bge m3 server
└── start_small_large_m3.sh    # Script to start bge small large m3 server
```
---

- **Last Updated**: 2026-01-30
- **Version**: 1.0.0 
- **Maintainers**: Temuulen  
- **Contact**: te100@duke.edu
