# Query

Use the agent.py's Agent to query. When searching the previous version had only two parameters (`current_user_message` and `question_id`), but now it has 3 more parameters:
- `user_id` accepts a `str`. Defaults to `Chat_DKU` if none given.
- `search_mode` accepts an `int`. Defaults to 0.
    - `search_mode == 0` means searching from the default corpus (chat_dku_advising)
    - `search_mode == 1` means searching from the user corpus 
    - `search_mode == 2` means searching from the both corpuses 
- `docs` accepts a `list of str`. List of names of the documents to be searched. When searching with modes 1 and 2, always give the documents' names to be searched. Defaults to `None`.

# User files update

Use the following to update user files. 

Import example:
`from chatdku.backend.user_data_interface import update` 

Honestly, you can import as how you wish. This is just an example.

> [!IMPORTANT]
> It assumes that you are using this function AFTER updating the files.

Args:
- `data_dir` - user's directory path
- `user_id` - user id

# User files remove

Use the following to delete files from the ChromaDB and Redis. It will automatically detect changes and remove the files from both databases.

Import example:
`from chatdku.backend.user_data_interface import remove`
> [!IMPORTANT]
> It assumes that you are using this function AFTER removing the files.

Honestly, you can import as how you wish. This is just an example.

Args:
- `data_dir` - user's directory path
- `user_id` - user id
 
