import React from "react";

/**
 * PUBLIC_INTERFACE
 * ErrorBoundary component to catch rendering/runtime errors and display a friendly fallback UI.
 * Use to wrap entire app or key dashboard areas to prevent a blank screen on unexpected exceptions.
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so next render shows fallback UI
    return { hasError: true, error, errorInfo: null };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ hasError: true, error, errorInfo });
    // Optionally log error to external service here
    if (process.env.NODE_ENV === "development") {
      console.error("ErrorBoundary caught:", error, errorInfo);
    }
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    // Optionally reload page or do other recovery
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          margin: "80px auto 40px auto",
          maxWidth: 490,
          padding: "32px",
          background: "#fffbe7",
          border: "2px solid #ffe2a8",
          borderRadius: "16px",
          textAlign: "center",
          color: "#ad3f32"
        }}>
          <h2>Something went wrong</h2>
          <p>
            The application encountered an unexpected error and could not display the dashboard.<br />
            If you just connected to the backend, try reloading.<br />
            <span style={{color: "#ff9900", fontWeight: 500}}>
              {this.state.error?.message?.toString().match(/Network Error|Failed to fetch|ECONNREFUSED/)
                ? "It looks like the backend service is unreachable."
                : null}
            </span>
          </p>
          <p style={{fontSize: "0.96em", color: "#a88334"}}>
            {this.state.error?.message ? String(this.state.error.message) : null}
          </p>
          <button onClick={this.handleReload} style={{marginTop: 18, padding: "12px 28px"}}>Reload</button>
          {this.state.errorInfo && (
            <details style={{whiteSpace: "pre-wrap", marginTop: 12}}>
              {this.state.errorInfo.componentStack}
            </details>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
