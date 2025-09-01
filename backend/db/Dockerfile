FROM postgres:15-alpine AS pgvector-builder

RUN apk add --no-cache git make gcc libc-dev clang llvm15 llvm15-dev postgresql15-dev postgresql15-contrib

RUN git clone --branch v0.4.4 https://github.com/pgvector/pgvector.git /tmp/pgvector

WORKDIR /tmp/pgvector

RUN make
RUN make install

FROM postgres:15-alpine

COPY --from=pgvector-builder /usr/local/lib/postgresql/bitcode/vector.index.bc /usr/local/lib/postgresql/bitcode/vector.index.bc
COPY --from=pgvector-builder /usr/local/lib/postgresql/vector.so /usr/local/lib/postgresql/vector.so
COPY --from=pgvector-builder /usr/local/share/postgresql/extension /usr/local/share/postgresql/extension

COPY postgresql.conf /usr/share/postgresql/postgresql.conf.sample
