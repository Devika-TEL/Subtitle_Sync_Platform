# Audio-Subtitle-Sync Frontend Web Dashboard

This frontend React app provides a dashboard for video subtitle correction and generation, integrating with the FastAPI backend.

## Development Setup

### 1. Install frontend dependencies

```bash
cd Subtitle_Sync_Platform/FrontendWebDashboard
npm install
```

### 2. Set the backend API base URL

Edit `.env` (or copy from `.env.example`):

```
REACT_APP_API_BASE_URL=https://vscode-internal-29567-beta.beta01.cloud.kavia.ai/proxy/8000/
```
- All API requests from the dashboard will use this endpoint by default.
- If your backend runs elsewhere or in production, set the correct API base URL.

### 3. Start the frontend dev server (runs on port 3000):

```bash
npm start
```

The preview version of the frontend app is accessed at:
```
https://vscode-internal-29567-beta.beta01.cloud.kavia.ai:3000/preview.html
```

### 4. Start the backend API server (if developing locally):

```bash
cd ../BackendService
uvicorn main:app --reload --port 8000
```
- If you change the backend port, update BOTH the backend start command and the `REACT_APP_API_BASE_URL` in your .env.

### Troubleshooting

- **CORS errors**: The backend is configured for CORS to accept requests from `http://localhost:3000` and proxy requests.
- **Connection errors**: Ensure both backend and frontend are running, check ports and the value of `REACT_APP_API_BASE_URL`.
- Visit `https://vscode-internal-29567-beta.beta01.cloud.kavia.ai/proxy/8000/` in your browser to check backend status.

If following these steps does not resolve the issue, check your browser's console network tab for CORS errors or request failures for further debugging.
