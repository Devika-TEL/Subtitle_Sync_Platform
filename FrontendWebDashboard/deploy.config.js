// Deployment Configuration for SubtitleSync Frontend
// This file contains deployment settings for different environments

const deployConfig = {
  // Development environment
  development: {
    apiBaseUrl: 'http://localhost:3001',
    siteUrl: 'http://localhost:3000',
    enableDebug: true,
    enableSourceMaps: true,
    enableHotReload: true,
    cacheStrategy: 'no-cache',
    errorReporting: false
  },

  // Staging environment
  staging: {
    apiBaseUrl: process.env.REACT_APP_API_BASE_URL || 'https://api-staging.subtitlesync.com',
    siteUrl: process.env.REACT_APP_SITE_URL || 'https://staging.subtitlesync.com',
    enableDebug: false,
    enableSourceMaps: true,
    enableHotReload: false,
    cacheStrategy: 'cache-first',
    errorReporting: true,
    errorReportingUrl: process.env.REACT_APP_ERROR_REPORTING_URL
  },

  // Production environment
  production: {
    apiBaseUrl: process.env.REACT_APP_API_BASE_URL || 'https://api.subtitlesync.com',
    siteUrl: process.env.REACT_APP_SITE_URL || 'https://subtitlesync.com',
    enableDebug: false,
    enableSourceMaps: false,
    enableHotReload: false,
    cacheStrategy: 'cache-first',
    errorReporting: true,
    errorReportingUrl: process.env.REACT_APP_ERROR_REPORTING_URL,
    analyticsId: process.env.REACT_APP_ANALYTICS_ID
  }
};

// Docker configuration
const dockerConfig = {
  // Multi-stage build configuration
  build: {
    nodeVersion: '18-alpine',
    workdir: '/app',
    buildCommand: 'npm run build',
    outputDir: 'build'
  },
  
  // Runtime configuration
  runtime: {
    baseImage: 'nginx:alpine',
    port: 80,
    nginxConfig: '/etc/nginx/conf.d/default.conf'
  }
};

// Nginx configuration for production
const nginxConfig = `
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html index.htm;

    # Handle client-side routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy (if needed)
    location /api/ {
        proxy_pass ${deployConfig.production.apiBaseUrl}/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private must-revalidate auth;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/x-javascript
        application/xml+rss
        application/javascript
        application/json;

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security - hide nginx version
    server_tokens off;
}
`;

// Kubernetes deployment configuration
const kubernetesConfig = {
  deployment: {
    name: 'subtitlesync-frontend',
    namespace: 'subtitlesync',
    replicas: 3,
    image: 'subtitlesync/frontend:latest',
    port: 80,
    resources: {
      requests: {
        cpu: '100m',
        memory: '128Mi'
      },
      limits: {
        cpu: '500m',
        memory: '512Mi'
      }
    }
  },
  
  service: {
    name: 'subtitlesync-frontend-service',
    type: 'ClusterIP',
    port: 80,
    targetPort: 80
  },
  
  ingress: {
    name: 'subtitlesync-frontend-ingress',
    host: 'subtitlesync.com',
    tls: true,
    annotations: {
      'kubernetes.io/ingress.class': 'nginx',
      'cert-manager.io/cluster-issuer': 'letsencrypt-prod'
    }
  }
};

module.exports = {
  deployConfig,
  dockerConfig,
  nginxConfig,
  kubernetesConfig
};
