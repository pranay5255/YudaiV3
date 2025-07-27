# Multi-stage build for React frontend
FROM node:18-alpine AS builder

# Install pnpm
RUN npm install -g pnpm

# Set work directory
WORKDIR /app

# Accept build args for environment variables
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

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

# For production, use nginx.prod.conf instead of nginx.conf
COPY ./nginx.prod.conf /etc/nginx/conf.d/default.conf

# Create health endpoint
RUN echo "healthy" > /usr/share/nginx/html/health

# Set proper permissions
RUN chmod -R 755 /usr/share/nginx/html

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"] 
