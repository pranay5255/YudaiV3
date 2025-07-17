-- PostgreSQL initialization script for YudaiV3
-- This script runs when the PostgreSQL container starts for the first time

-- Create the database if it doesn't exist (PostgreSQL creates it automatically from env vars)
-- But we can add any additional setup here

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE yudai_db TO yudai_user;

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Set timezone
SET timezone = 'UTC';

-- Log initialization
SELECT 'YudaiV3 database initialized successfully' as status; 