CREATE ROLE chatdku_readonly LOGIN PASSWORD 'alohomora';
GRANT CONNECT ON DATABASE chatdku_db TO chatdku_readonly;
GRANT USAGE ON SCHEMA public TO chatdku_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO chatdku_readonly;
