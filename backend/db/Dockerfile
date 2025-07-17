FROM postgres:15-alpine

# Set environment variables
ENV POSTGRES_DB=yudai_db
ENV POSTGRES_USER=yudai_user
ENV POSTGRES_PASSWORD=yudai_password

# Create directory for initialization scripts
RUN mkdir -p /docker-entrypoint-initdb.d

# Copy initialization scripts
COPY init.sql /docker-entrypoint-initdb.d/

# Expose PostgreSQL port
EXPOSE 5432

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD pg_isready -U $POSTGRES_USER -d $POSTGRES_DB || exit 1 
