# Audio-Subtitle-Sync Frontend Web Dashboard

This frontend React app provides a dashboard for video subtitle correction and generation, integrating with the FastAPI backend.

## Development Setup

### 1. Install frontend dependencies

```bash
cd Subtitle_Sync_Platform/FrontendWebDashboard
npm install
```

### 2. Set the backend API base URL (default backend: http://localhost:3001):

Edit `.env` (or copy from `.env.example`):

```
REACT_APP_API_BASE=http://localhost:3001
```
- If your backend runs elsewhere or in production, set the correct API base.

### 3. Start the frontend dev server (runs on port 3000):

```bash
npm start
```

### 4. Start the backend API server (expected on port 3001):

```bash
cd ../BackendService
uvicorn main:app --reload --port 3001
```
- If you change the backend port, update BOTH the backend start command and the `REACT_APP_API_BASE` in your .env.

### Troubleshooting

- **CORS errors**: The backend is configured for CORS to accept requests from `http://localhost:3000` and `http://localhost:3001`.
- **Connection errors**: Ensure both backend and frontend are running, check ports and the value of `REACT_APP_API_BASE`.
- **Changing ports**: If you run the backend on a port other than 3001, update BOTH backend launch and frontend `.env`.
- Visit `http://localhost:3001/api/health` in your browser to check backend status.

If following these steps does not resolve the issue, check your browser's console network tab for CORS errors or request failures for further debugging.
