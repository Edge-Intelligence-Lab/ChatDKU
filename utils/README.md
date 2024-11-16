# Utilities

## `test_backend.sh`

Send a chat request to the ChatDKU backend running at the specific port. You can optionally specific the chat message content, which defaults to `"What do you know about DKU?"`.
```bash
./test_backend.sh <port> [content]
```

## `data_count_size.sh`

Run
```bash
./data_count_size.sh
```
to count the number of files and their total sizes grouped by their extensions in
`../RAG_data`.

__TODO: Allow user to pass in an arbitrary directory via commandline arguments.__

## `save_tokenizer.py`

Save the tokenizer of an LLM from Hugging Face to a local directory.

## `test_redis`

Example and testing code for working with Redis.
