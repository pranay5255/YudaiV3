# Use pre-built pgvector image as base (includes pgvector extension)
FROM pgvector/pgvector:pg15

# Set environment variables for database initialization
ENV POSTGRES_DB=yudai_dev
ENV POSTGRES_USER=yudai_user
ENV POSTGRES_PASSWORD=yudai_password

# Copy initialization scripts to run on first startup
COPY init.sql /docker-entrypoint-initdb.d/01-init.sql

# Set proper permissions for init script
RUN chmod 644 /docker-entrypoint-initdb.d/01-init.sql

# Copy Python scripts for potential runtime use
COPY init_db.py /usr/local/bin/
COPY database.py /usr/local/bin/
RUN chmod +x /usr/local/bin/init_db.py
