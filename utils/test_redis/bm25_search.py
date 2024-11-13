from redis import Redis
from redis.commands.search.query import Query

client = Redis.from_url("redis://localhost:6379")


def search_and_filter(query_str: str, groups: list[str]):
    params = {"query_str": query_str}
    for i, g in enumerate(groups):
        params[f"group_{i}"] = g
    groups_str = " | ".join([f"$group_{i}" for i in range(len(groups))])
    query = (
        Query(f"@text:$query_str @groups:{{ {groups_str} }}").dialect(2).scorer("BM25")
    )

    results = client.ft("idx:test").search(query, params)
    for doc in results.docs:
        print(f"ID: {doc.id}, Text: {doc.text}, Groups: {doc.groups}")


search_and_filter("quick", ["supervisor"])
print("---")
search_and_filter("quick", ["supervisor", "public"])
