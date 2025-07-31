#!/bin/sh

# Docker entrypoint script for SubtitleSync Frontend
# Injects environment variables into the React build at runtime

set -e

# Function to log messages
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting SubtitleSync Frontend container..."

# Environment variables that can be injected at runtime
RUNTIME_VARS="
REACT_APP_API_BASE_URL
REACT_APP_SITE_URL
REACT_APP_VERSION
REACT_APP_ENABLE_DEBUG
REACT_APP_ENABLE_ANALYTICS
"

# Path to the main JS file (this will vary based on build)
JS_FILE=$(find /usr/share/nginx/html/static/js -name "main.*.js" -type f | head -1)

if [ -n "$JS_FILE" ]; then
    log "Found main JS file: $JS_FILE"
    
    # Create a backup of the original file
    cp "$JS_FILE" "$JS_FILE.backup"
    
    # Replace environment variables in the JS file
    for var in $RUNTIME_VARS; do
        if [ -n "$(eval echo \$$var)" ]; then
            log "Injecting $var with value: $(eval echo \$$var)"
            # Replace placeholder with actual value
            sed -i "s|PLACEHOLDER_${var}|$(eval echo \$$var)|g" "$JS_FILE"
        else
            log "Environment variable $var not set, using default"
        fi
    done
else
    log "Warning: Could not find main JS file for environment variable injection"
fi

# Inject environment variables into index.html
INDEX_FILE="/usr/share/nginx/html/index.html"

if [ -f "$INDEX_FILE" ]; then
    log "Injecting environment variables into index.html"
    
    # Create runtime configuration object
    cat > /usr/share/nginx/html/config.js << EOF
window.APP_CONFIG = {
    API_BASE_URL: '${REACT_APP_API_BASE_URL:-http://localhost:3001}',
    SITE_URL: '${REACT_APP_SITE_URL:-http://localhost:3000}',
    VERSION: '${REACT_APP_VERSION:-1.0.0}',
    ENABLE_DEBUG: ${REACT_APP_ENABLE_DEBUG:-false},
    ENABLE_ANALYTICS: ${REACT_APP_ENABLE_ANALYTICS:-false}
};
EOF
    
    # Inject script tag into HTML head
    sed -i 's|</head>|<script src="/config.js"></script></head>|' "$INDEX_FILE"
fi

# Validate nginx configuration
log "Validating nginx configuration..."
nginx -t

log "Environment setup complete. Starting nginx..."

# Execute the main command
exec "$@"
