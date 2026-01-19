# 1. 连接数据库删除旧表
psql -h localhost -U chatdku_user -d chatdku_db -c "DROP TABLE IF EXISTS dku_class_schedule;"

# 2. 创建新表
psql -h localhost -U chatdku_user -d chatdku_db -f /home/zhiwei531/ChatDKU/chatdku/chatdku/core/tools/course_schedule/create_table.sql

# 3. 运行 ingestion
export DB_PWD="securepassword123"
python3 -m chatdku.chatdku.core.tools.course_schedule.ingest 