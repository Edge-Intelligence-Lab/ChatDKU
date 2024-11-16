# -*- coding: utf-8 -*-

from redis import Redis
from redis.commands.search.query import Query

client = Redis.from_url("redis://localhost:6379")

# Add a document
# client.hset("cn:doc", "txt", 'Redis支持主从同步。数据可以从主服务器向任意数量的从服务器上同步从服务器可以是关联其他从服务器的主服务器。这使得Redis可执行单层树复制。从盘可以有意无意的对数据进行写操作。由于完全实现了发布/订阅机制，使得从数据库在任何地方同步树时，可订阅一个频道并接收主服务器完整的消息发布记录。同步对读取操作的可扩展性和数据冗余很有帮助。[8]')

# client.hset("cn:doc", "txt", 'Redis Quick Brown支持主从同步。数据可以从主服务器向任意数量的从服务器上同步从服务器可以是关联其他从服务器的主服务器。这使得Redis可执行单层树复制。从盘可以有意无意的对数据进行写操作。由于完全实现了发布/订阅机制，使得从数据库在任何地方同步树时，可订阅一个频道并接收主服务器完整的消息发布记录。同步对读取操作的可扩展性和数据冗余很有帮助。[8]')

# client.hset("cn:doc1", "txt", '一个两个单词')

client.hset("cn:doc2", "txt", 'jumping test')

# print(client.ft("idx:cn").search(Query('支持同步').summarize().highlight()).docs[0].txt)

query = Query('$query_str').summarize().highlight().language("chinese").dialect(2)
params = {"query_str": "jumping"}
print(client.ft("idx:cn").search(query, params).docs[0].txt)

# Outputs:
# <b>数据</b>?... <b>数据</b>进行写操作。由于完全实现了发布... <b>数据</b>冗余很有帮助。[8...
