import React from 'react';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import App from './App';

// Mock the AuthContext to avoid dependency issues in tests
jest.mock('./contexts/AuthContext', () => ({
  AuthProvider: ({ children }) => <div data-testid="auth-provider">{children}</div>,
  useAuth: () => ({
    user: null,
    loading: false,
    login: jest.fn(),
    register: jest.fn(),
    logout: jest.fn(),
    isAuthenticated: false,
    isAdmin: false
  })
}));

// Mock components that might have complex dependencies
jest.mock('./components/SubtitleEditor/SubtitleEditor', () => {
  return function MockSubtitleEditor() {
    return <div data-testid="subtitle-editor">Subtitle Editor</div>;
  };
});

jest.mock('./components/NotificationSystem/NotificationSystem', () => {
  return function MockNotificationSystem() {
    return <div data-testid="notification-system">Notification System</div>;
  };
});

describe('App Component', () => {
  const renderApp = () => {
    return render(<App />);
  };

  beforeEach(() => {
    // Clear any previous global methods
    delete window.showNotification;
    delete window.clearNotifications;
  });

  test('renders without crashing', () => {
    renderApp();
    expect(screen.getByTestId('auth-provider')).toBeInTheDocument();
  });

  test('renders notification system', () => {
    renderApp();
    expect(screen.getByTestId('notification-system')).toBeInTheDocument();
  });

  test('renders auth page when user is not logged in', () => {
    renderApp();
    // Should render auth page components
    expect(screen.getByText(/SubtitleSync/i)).toBeInTheDocument();
  });
});

describe('App Integration', () => {
  test('handles error boundary correctly', () => {
    // Suppress console.error for this test
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    
    const ThrowError = () => {
      throw new Error('Test error');
    };

    const AppWithError = () => (
      <App>
        <ThrowError />
      </App>
    );

    render(<AppWithError />);
    
    // Should render error boundary instead of crashing
    expect(screen.queryByText('Test error')).not.toBeInTheDocument();
    
    consoleSpy.mockRestore();
  });
});
