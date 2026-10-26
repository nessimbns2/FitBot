-- FitBot : création du rôle applicatif et de la base PostgreSQL
-- À exécuter UNE fois en tant que superutilisateur (postgres), par ex. dans pgAdmin > Query Tool
-- sur la base "postgres". Les tables sont ensuite créées par Alembic (backend: alembic upgrade head)
-- ou par database/schema.sql.

CREATE ROLE fitbot WITH LOGIN CREATEDB PASSWORD 'CHANGE_ME_same_as_DATABASE_URL_in_backend_env';
CREATE DATABASE fitbot_db OWNER fitbot ENCODING 'UTF8' TEMPLATE template0;
GRANT ALL PRIVILEGES ON DATABASE fitbot_db TO fitbot;
