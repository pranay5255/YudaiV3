FROM postgres:15-alpine

# Install pgvector extension
RUN apk add --no-cache git build-base postgresql-dev && \
    cd /tmp && \
    git clone https://github.com/pgvector/pgvector.git && \
    cd pgvector && \
    # Remove LLVM bitcode compilation targets from Makefile
    sed -i '/\.bc$/d' Makefile && \
    sed -i '/clang.*-emit-llvm/d' Makefile && \
    sed -i '/LLVM/d' Makefile && \
    # Build without LLVM support
    make && \
    make install && \
    cd / && rm -rf /tmp/pgvector

# Set environment variables for database (provided at runtime)
# Postgres configuration
ENV POSTGRES_INITDB_ARGS="--encoding=UTF8 --locale=C"
ENV POSTGRES_HOST_AUTH_METHOD=trust

# Configure PostgreSQL for better performance
RUN echo "listen_addresses = '*'" >> /usr/local/share/postgresql/postgresql.conf.sample && \
    echo "max_connections = 200" >> /usr/local/share/postgresql/postgresql.conf.sample && \
    echo "shared_buffers = 256MB" >> /usr/local/share/postgresql/postgresql.conf.sample && \
    echo "effective_cache_size = 1GB" >> /usr/local/share/postgresql/postgresql.conf.sample && \
    echo "work_mem = 4MB" >> /usr/local/share/postgresql/postgresql.conf.sample && \
    echo "maintenance_work_mem = 64MB" >> /usr/local/share/postgresql/postgresql.conf.sample

# Create directory for initialization scripts
RUN mkdir -p /docker-entrypoint-initdb.d

# Copy initialization scripts
COPY init.sql /docker-entrypoint-initdb.d/

# Expose PostgreSQL port
EXPOSE 5432

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD pg_isready -U $POSTGRES_USER -d $POSTGRES_DB || exit 1 
