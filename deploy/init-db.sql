-- Runs once, the first time the Postgres volume is created.
CREATE DATABASE keycloak;
\c hga
CREATE EXTENSION IF NOT EXISTS vector;
