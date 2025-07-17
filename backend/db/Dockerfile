FROM postgres:15-alpine

# Install Python and required packages using system package manager
# This avoids the externally-managed-environment issue
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-sqlalchemy \
    py3-psycopg2 \
    py3-pydantic

# Set environment variables
ENV POSTGRES_DB=yudai_db
ENV POSTGRES_USER=yudai_user
ENV POSTGRES_PASSWORD=yudai_password

# Create directory for initialization scripts
RUN mkdir -p /docker-entrypoint-initdb.d

# Copy initialization scripts
COPY init.sql /docker-entrypoint-initdb.d/

# Create a directory for Python scripts
RUN mkdir -p /app

# Copy the combined Python initialization script
COPY init_db.py /app/

# Copy the Python initialization script
COPY init_python.sh /docker-entrypoint-initdb.d/

# Make the script executable
RUN chmod +x /docker-entrypoint-initdb.d/init_python.sh

# Expose PostgreSQL port
EXPOSE 5432

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD pg_isready -U $POSTGRES_USER -d $POSTGRES_DB || exit 1 
