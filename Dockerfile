# Multi-stage build for React frontend
FROM node:18-alpine AS builder

# Install pnpm
RUN npm install -g pnpm

# Set work directory
WORKDIR /app

# Accept build args for environment variables
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Copy package files
COPY package*.json pnpm-lock.yaml* ./

# Install dependencies using pnpm
RUN pnpm install

# Copy source code
COPY . .

# Build the application
RUN pnpm run build

# Verify build output
RUN ls -la /app/dist/ && test -f /app/dist/index.html

# Production stage
FROM nginx:alpine

# Copy built app from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy the nginx configuration (supports dev/prod configs)
RUN rm -f /etc/nginx/nginx.conf
COPY nginx.prod.conf /etc/nginx/nginx.conf

# Copy nginx templates directory
COPY nginx/templates /etc/nginx/templates

# Create health endpoint
RUN echo "healthy" > /usr/share/nginx/html/health

# Set proper permissions
RUN chmod -R 755 /usr/share/nginx/html

# Expose ports (HTTP and HTTPS for production)
EXPOSE 80 443

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"] 
