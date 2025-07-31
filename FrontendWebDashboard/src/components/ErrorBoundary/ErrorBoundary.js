import React from 'react';
import './ErrorBoundary.css';

// PUBLIC_INTERFACE
/**
 * ErrorBoundary component that catches JavaScript errors in child components
 * Provides fallback UI and error reporting capabilities
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      eventId: null
    };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log error details
    const errorDetails = {
      error: error.toString(),
      errorInfo: errorInfo.componentStack,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href
    };

    console.error('ErrorBoundary caught an error:', errorDetails);

    // Update state with error details
    this.setState({
      error,
      errorInfo,
      eventId: Date.now().toString()
    });

    // Report error to external service (if configured)
    if (process.env.REACT_APP_ERROR_REPORTING_URL) {
      this.reportError(errorDetails);
    }
  }

  // PUBLIC_INTERFACE
  /**
   * Report error to external error tracking service
   * @param {Object} errorDetails - Error information
   */
  reportError = async (errorDetails) => {
    try {
      await fetch(process.env.REACT_APP_ERROR_REPORTING_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...errorDetails,
          level: 'error',
          platform: 'frontend',
          component: 'ErrorBoundary'
        })
      });
    } catch (reportingError) {
      console.error('Failed to report error:', reportingError);
    }
  };

  // PUBLIC_INTERFACE
  /**
   * Reset error boundary state
   */
  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      eventId: null
    });
  };

  // PUBLIC_INTERFACE
  /**
   * Reload the entire application
   */
  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      const { fallback: FallbackComponent } = this.props;
      
      // Use custom fallback component if provided
      if (FallbackComponent) {
        return (
          <FallbackComponent
            error={this.state.error}
            errorInfo={this.state.errorInfo}
            eventId={this.state.eventId}
            onReset={this.handleReset}
            onReload={this.handleReload}
          />
        );
      }

      // Default error UI
      return (
        <div className="error-boundary">
          <div className="error-boundary-container">
            <div className="error-boundary-header">
              <div className="error-icon">⚠️</div>
              <h1 className="error-title">Something went wrong</h1>
              <p className="error-subtitle">
                We're sorry, but something unexpected happened. Please try refreshing the page.
              </p>
            </div>

            <div className="error-boundary-actions">
              <button 
                className="btn primary"
                onClick={this.handleReload}
              >
                <span>🔄</span>
                Reload Page
              </button>
              <button 
                className="btn secondary"
                onClick={this.handleReset}
              >
                <span>↩️</span>
                Try Again
              </button>
            </div>

            {process.env.NODE_ENV === 'development' && (
              <div className="error-boundary-details">
                <details className="error-details-toggle">
                  <summary>View Error Details (Development Mode)</summary>
                  <div className="error-details-content">
                    <div className="error-section">
                      <h3>Error:</h3>
                      <pre className="error-code">
                        {this.state.error && this.state.error.toString()}
                      </pre>
                    </div>
                    
                    <div className="error-section">
                      <h3>Component Stack:</h3>
                      <pre className="error-code">
                        {this.state.errorInfo && this.state.errorInfo.componentStack}
                      </pre>
                    </div>
                    
                    <div className="error-section">
                      <h3>Error ID:</h3>
                      <code>{this.state.eventId}</code>
                    </div>
                  </div>
                </details>
              </div>
            )}

            <div className="error-boundary-footer">
              <p className="error-help-text">
                If this problem persists, please contact support with Error ID: 
                <strong> {this.state.eventId}</strong>
              </p>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
