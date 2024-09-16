from redis import Redis
from redis.commands.search.query import Query

client = Redis.from_url("redis://localhost:6379")


def search_and_filter(query_str: str):
    params = {"query_str": query_str}
    # for i, g in enumerate(groups):
    #     params[f"group_{i}"] = g
    # groups_str = " | ".join([f"$group_{i}" for i in range(len(groups))])
    query = (
        Query(f"@text:$query_str").dialect(2).scorer("BM25")
    )

    results = client.ft("idx:test").search(query, params)
    for doc in results.docs:
        # print(doc)
        print(f"ID: {doc.id}, file_path:{doc.filename}")



search_and_filter("2025bulletin")
print("---")

