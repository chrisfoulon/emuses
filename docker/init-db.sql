-- Initialize EMUSES database with required extensions and configurations

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search optimization

-- Create additional indexes for performance
-- These will be created by SQLAlchemy migrations, but we ensure they exist

-- Grant permissions for application user
GRANT ALL PRIVILEGES ON DATABASE emuses_db TO emuses_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO emuses_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO emuses_user;

-- Set up connection limits and performance tuning
ALTER DATABASE emuses_db SET shared_preload_libraries = 'pg_stat_statements';
ALTER DATABASE emuses_db SET log_min_duration_statement = 1000;  -- Log slow queries
ALTER DATABASE emuses_db SET log_statement = 'mod';  -- Log modifications

-- Create a read-only user for monitoring/analytics (optional)
CREATE USER emuses_readonly WITH PASSWORD 'readonly_password_change_in_production';
GRANT CONNECT ON DATABASE emuses_db TO emuses_readonly;
GRANT USAGE ON SCHEMA public TO emuses_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO emuses_readonly;

-- Ensure future tables are accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO emuses_readonly;