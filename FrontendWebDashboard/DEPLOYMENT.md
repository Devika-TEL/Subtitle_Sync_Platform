# SubtitleSync Frontend - Deployment Guide

Complete guide for deploying the SubtitleSync React frontend application in different environments.

## Quick Start

### Local Development
```bash
# Install dependencies
npm install

# Start development server
npm start

# Application will be available at http://localhost:3000
```

### Production Build
```bash
# Create optimized production build
npm run build

# Serve locally for testing
npm run serve
```

## Environment Configuration

### Required Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Core configuration
REACT_APP_API_BASE_URL=http://localhost:3001
REACT_APP_SITE_URL=http://localhost:3000

# Optional features
REACT_APP_ENABLE_EDITOR=true
REACT_APP_ENABLE_FILE_MANAGER=true
REACT_APP_ENABLE_TRANSLATIONS=true
```

### Environment-Specific Configurations

#### Development
```bash
REACT_APP_API_BASE_URL=http://localhost:3001
REACT_APP_SITE_URL=http://localhost:3000
REACT_APP_DEBUG_MODE=true
```

#### Staging
```bash
REACT_APP_API_BASE_URL=https://api-staging.subtitlesync.com
REACT_APP_SITE_URL=https://staging.subtitlesync.com
REACT_APP_DEBUG_MODE=false
```

#### Production
```bash
REACT_APP_API_BASE_URL=https://api.subtitlesync.com
REACT_APP_SITE_URL=https://subtitlesync.com
REACT_APP_DEBUG_MODE=false
GENERATE_SOURCEMAP=false
```

## Deployment Methods

### 1. Static Hosting (Netlify, Vercel, AWS S3)

#### Netlify
1. Connect your repository to Netlify
2. Set build command: `npm run build`
3. Set publish directory: `build`
4. Configure environment variables in Netlify dashboard
5. Enable redirect rules for SPA routing:

```bash
# Create _redirects file in public folder
/*    /index.html   200
```

#### Vercel
1. Install Vercel CLI: `npm i -g vercel`
2. Run: `vercel --prod`
3. Configure environment variables in Vercel dashboard

#### AWS S3 + CloudFront
```bash
# Build the application
npm run build

# Sync to S3 bucket
aws s3 sync build/ s3://your-bucket-name --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id YOUR_DISTRIBUTION_ID --paths "/*"
```

### 2. Docker Deployment

#### Build Docker Image
```bash
# Build with default configuration
docker build -t subtitlesync-frontend .

# Build with custom environment variables
docker build \
  --build-arg REACT_APP_API_BASE_URL=https://api.subtitlesync.com \
  --build-arg REACT_APP_SITE_URL=https://subtitlesync.com \
  -t subtitlesync-frontend:prod .
```

#### Run Docker Container
```bash
# Run with default configuration
docker run -p 80:80 subtitlesync-frontend

# Run with runtime environment variables
docker run -p 80:80 \
  -e REACT_APP_API_BASE_URL=https://api.subtitlesync.com \
  -e REACT_APP_SITE_URL=https://subtitlesync.com \
  subtitlesync-frontend:prod
```

#### Docker Compose
```yaml
version: '3.8'
services:
  frontend:
    build: .
    ports:
      - "80:80"
    environment:
      - REACT_APP_API_BASE_URL=https://api.subtitlesync.com
      - REACT_APP_SITE_URL=https://subtitlesync.com
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80/"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 3. Kubernetes Deployment

#### Deployment Manifest
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: subtitlesync-frontend
  namespace: subtitlesync
spec:
  replicas: 3
  selector:
    matchLabels:
      app: subtitlesync-frontend
  template:
    metadata:
      labels:
        app: subtitlesync-frontend
    spec:
      containers:
      - name: frontend
        image: subtitlesync/frontend:latest
        ports:
        - containerPort: 80
        env:
        - name: REACT_APP_API_BASE_URL
          value: "https://api.subtitlesync.com"
        - name: REACT_APP_SITE_URL
          value: "https://subtitlesync.com"
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 512Mi
        livenessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 5
```

#### Service and Ingress
```yaml
---
apiVersion: v1
kind: Service
metadata:
  name: subtitlesync-frontend-service
  namespace: subtitlesync
spec:
  selector:
    app: subtitlesync-frontend
  ports:
  - port: 80
    targetPort: 80
  type: ClusterIP

---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: subtitlesync-frontend-ingress
  namespace: subtitlesync
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/use-regex: "true"
spec:
  tls:
  - hosts:
    - subtitlesync.com
    secretName: subtitlesync-tls
  rules:
  - host: subtitlesync.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: subtitlesync-frontend-service
            port:
              number: 80
```

### 4. Traditional Server Deployment

#### Nginx Configuration
```nginx
server {
    listen 80;
    server_name subtitlesync.com www.subtitlesync.com;
    root /var/www/subtitlesync/build;
    index index.html index.htm;

    # Handle client-side routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
}
```

#### Apache Configuration
```apache
<VirtualHost *:80>
    ServerName subtitlesync.com
    DocumentRoot /var/www/subtitlesync/build
    
    # Handle client-side routing
    <Directory "/var/www/subtitlesync/build">
        RewriteEngine On
        RewriteBase /
        RewriteRule ^index\.html$ - [L]
        RewriteCond %{REQUEST_FILENAME} !-f
        RewriteCond %{REQUEST_FILENAME} !-d
        RewriteRule . /index.html [L]
    </Directory>
    
    # Cache static assets
    <LocationMatch "\.(js|css|png|jpg|jpeg|gif|ico|svg)$">
        ExpiresActive On
        ExpiresDefault "access plus 1 year"
    </LocationMatch>
</VirtualHost>
```

## CI/CD Pipeline

### GitHub Actions
```yaml
name: Deploy Frontend

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'
        cache: 'npm'
    - run: npm ci
    - run: npm run test:ci
    - run: npm run build

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
    - uses: actions/checkout@v3
    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'
        cache: 'npm'
    - run: npm ci
    - run: npm run build
      env:
        REACT_APP_API_BASE_URL: ${{ secrets.API_BASE_URL }}
        REACT_APP_SITE_URL: ${{ secrets.SITE_URL }}
    - name: Deploy to S3
      run: aws s3 sync build/ s3://${{ secrets.S3_BUCKET }} --delete
      env:
        AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
        AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## Monitoring and Analytics

### Health Checks
The application includes health check endpoints:
- `GET /` - Returns application status
- Service worker provides offline functionality

### Performance Monitoring
```javascript
// Add to index.js for performance monitoring
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/service-worker.js');
}

// Web Vitals monitoring
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals';

getCLS(console.log);
getFID(console.log);
getFCP(console.log);
getLCP(console.log);
getTTFB(console.log);
```

### Error Tracking
Configure error reporting service in `.env`:
```bash
REACT_APP_ERROR_REPORTING_URL=https://your-error-service.com/api/errors
REACT_APP_SENTRY_DSN=your-sentry-dsn
```

## Security Considerations

### Content Security Policy
```html
<meta http-equiv="Content-Security-Policy" 
      content="default-src 'self'; 
               script-src 'self' 'unsafe-inline'; 
               style-src 'self' 'unsafe-inline'; 
               img-src 'self' data: blob: https:;">
```

### Environment Variables Security
- Never commit `.env` files to version control
- Use different `.env` files for different environments
- Rotate API keys and tokens regularly
- Use secret management systems in production

## Troubleshooting

### Common Issues

#### Build Fails
```bash
# Clear cache and rebuild
npm run clean
npm install
npm run build
```

#### Runtime Environment Variables Not Working
- Ensure variables start with `REACT_APP_`
- Check Docker environment variable injection
- Verify build-time vs runtime variable handling

#### Client-Side Routing Issues
- Configure web server to serve `index.html` for all routes
- Check redirect rules in hosting platform
- Verify `basename` configuration in React Router

#### Performance Issues
```bash
# Analyze bundle size
npm run build:analyze

# Check for unused dependencies
npx depcheck

# Optimize images and assets
npx imagemin-cli build/static/media/* --out-dir=build/static/media/
```

## Support

For deployment support:
- Check the GitHub Issues for known problems
- Review application logs for error details
- Contact the development team for assistance

---

**SubtitleSync Frontend Deployment** - Comprehensive deployment guide for production environments.
