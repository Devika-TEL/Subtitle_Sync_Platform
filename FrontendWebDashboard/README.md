# Lightweight React Template for KAVIA

This project provides a minimal React template with a clean, modern UI and minimal dependencies.

## Features

- **Lightweight**: No heavy UI frameworks - uses only vanilla CSS and React
- **Modern UI**: Clean, responsive design with KAVIA brand styling
- **Fast**: Minimal dependencies for quick loading times
- **Simple**: Easy to understand and modify

## Getting Started

In the project directory, you can run:

### `npm start`

Runs the app in development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

### `npm test`

Launches the test runner in interactive watch mode.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

## Customization

### Colors

The main brand colors are defined as CSS variables in `src/App.css`:

```css
:root {
  --kavia-orange: #E87A41;
  --kavia-dark: #1A1A1A;
  --text-color: #ffffff;
  --text-secondary: rgba(255, 255, 255, 0.7);
  --border-color: rgba(255, 255, 255, 0.1);
}
```

### Components

This template uses pure HTML/CSS components instead of a UI framework. You can find component styles in `src/App.css`. 

Common components include:
- Buttons (`.btn`, `.btn-large`)
- Container (`.container`)
- Navigation (`.navbar`)
- Typography (`.title`, `.subtitle`, `.description`)

## Learn More

To learn React, check out the [React documentation](https://reactjs.org/).

### Code Splitting

This section has moved here: [https://facebook.github.io/create-react-app/docs/code-splitting](https://facebook.github.io/create-react-app/docs/code-splitting)

### Analyzing the Bundle Size

This section has moved here: [https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size](https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size)

### Making a Progressive Web App

This section has moved here: [https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app](https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app)

### Advanced Configuration

This section has moved here: [https://facebook.github.io/create-react-app/docs/advanced-configuration](https://facebook.github.io/create-react-app/docs/advanced-configuration)

### Deployment

This section has moved here: [https://facebook.github.io/create-react-app/docs/deployment](https://facebook.github.io/create-react-app/docs/deployment)

### `npm run build` fails to minify

This section has moved here: [https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify](https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify)

---

## Troubleshooting: "Failed to fetch" on Submit

If you see a "Failed to fetch" error when submitting a correction or subtitle generation job, it usually means the frontend could not reach the backend API. This can be caused by:

- The backend server is not running, or running on the wrong port/address.
- The `REACT_APP_API_BASE` environment variable is incorrect or not set.
- There is a CORS (cross-origin resource sharing) configuration problem.
- Network/proxy/firewall issues.

**Steps to resolve:**

1. Make sure your backend server (FastAPI) is running, e.g. at http://localhost:8000.
2. Set the correct API base URL in your frontend environment:
   - Copy `.env.example` to `.env` in this folder.
   - Edit `.env` and set `REACT_APP_API_BASE` to match your backend, e.g.:
     ```
     REACT_APP_API_BASE=http://localhost:8000
     ```
3. Restart the frontend dev server after changing `.env`.
4. Visit `http://localhost:8000/api/health` in your browser to check backend status.
5. The backend CORS settings are permissive (see FastAPI CORSMiddleware in `main.py`), but if you have customized these, ensure your frontend origin is allowed.

If following these steps does not resolve the issue, check your browser's console network tab for CORS errors or request failures for further debugging.
