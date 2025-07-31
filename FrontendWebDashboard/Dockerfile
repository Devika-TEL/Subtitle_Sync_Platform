# Multi-stage build for SubtitleSync Frontend
# Stage 1: Build the React application

FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Add metadata
LABEL maintainer="SubtitleSync Team <support@subtitlesync.com>"
LABEL description="SubtitleSync Frontend - React Application"
LABEL version="1.0.0"

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production --silent

# Copy source code
COPY . .

# Build arguments for environment configuration
ARG REACT_APP_API_BASE_URL
ARG REACT_APP_SITE_URL
ARG REACT_APP_VERSION=1.0.0
ARG NODE_ENV=production

# Set environment variables
ENV NODE_ENV=$NODE_ENV
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL
ENV REACT_APP_SITE_URL=$REACT_APP_SITE_URL
ENV REACT_APP_VERSION=$REACT_APP_VERSION
ENV GENERATE_SOURCEMAP=false

# Build the application
RUN npm run build

# Stage 2: Production server with Nginx
FROM nginx:alpine

# Install additional tools
RUN apk add --no-cache \
    curl \
    jq

# Copy built application from builder stage
COPY --from=builder /app/build /usr/share/nginx/html

# Copy custom nginx configuration
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy custom index.html with environment variable injection script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create non-root user for security
RUN addgroup -g 1001 -S nginx-user && \
    adduser -S -D -H -u 1001 -h /var/cache/nginx -s /sbin/nologin -G nginx-user -g nginx-user nginx-user

# Set ownership and permissions
RUN chown -R nginx-user:nginx-user /usr/share/nginx/html && \
    chown -R nginx-user:nginx-user /var/cache/nginx && \
    chown -R nginx-user:nginx-user /var/log/nginx && \
    chown -R nginx-user:nginx-user /etc/nginx/conf.d

# Switch to non-root user
USER nginx-user

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/ || exit 1

# Expose port
EXPOSE 80

# Use custom entrypoint for environment variable injection
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
