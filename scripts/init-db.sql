SELECT 'CREATE DATABASE atlas_intel_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'atlas_intel_test')
\gexec

\connect atlas_intel
CREATE EXTENSION IF NOT EXISTS pg_trgm;

\connect atlas_intel_test
CREATE EXTENSION IF NOT EXISTS pg_trgm;
