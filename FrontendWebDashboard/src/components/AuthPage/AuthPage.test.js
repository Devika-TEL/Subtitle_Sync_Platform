import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AuthPage from './AuthPage';

// Mock the AuthContext
const mockLogin = jest.fn();
const mockRegister = jest.fn();

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    login: mockLogin,
    register: mockRegister,
    loading: false,
    error: null
  })
}));

// Mock the global notification function
global.window.showNotification = jest.fn();

describe('AuthPage Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Login Mode', () => {
    test('renders login form by default', () => {
      render(<AuthPage />);
      
      expect(screen.getByText('Welcome back!')).toBeInTheDocument();
      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    });

    test('validates required fields', async () => {
      const user = userEvent.setup();
      render(<AuthPage />);
      
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);
      
      expect(screen.getByText('Email is required')).toBeInTheDocument();
      expect(screen.getByText('Password is required')).toBeInTheDocument();
    });

    test('validates email format', async () => {
      const user = userEvent.setup();
      render(<AuthPage />);
      
      const emailInput = screen.getByLabelText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      
      await user.type(emailInput, 'invalid-email');
      await user.click(submitButton);
      
      expect(screen.getByText('Please enter a valid email address')).toBeInTheDocument();
    });

    test('submits login form with valid data', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValue({ token: 'test-token' });
      
      render(<AuthPage />);
      
      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123');
      });
    });
  });

  describe('Registration Mode', () => {
    test('renders registration form when mode is register', () => {
      render(<AuthPage mode="register" />);
      
      expect(screen.getByText('Join us today!')).toBeInTheDocument();
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
    });

    test('validates password confirmation', async () => {
      const user = userEvent.setup();
      render(<AuthPage mode="register" />);
      
      const passwordInput = screen.getByLabelText(/^password/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /create account/i });
      
      await user.type(passwordInput, 'password123');
      await user.type(confirmPasswordInput, 'different-password');
      await user.click(submitButton);
      
      expect(screen.getByText('Passwords do not match')).toBeInTheDocument();
    });

    test('validates terms acceptance', async () => {
      const user = userEvent.setup();
      render(<AuthPage mode="register" />);
      
      const usernameInput = screen.getByLabelText(/username/i);
      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/^password/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /create account/i });
      
      await user.type(usernameInput, 'testuser');
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.type(confirmPasswordInput, 'password123');
      await user.click(submitButton);
      
      expect(screen.getByText('You must accept the terms and conditions')).toBeInTheDocument();
    });
  });

  describe('Mode Switching', () => {
    test('switches from login to register mode', async () => {
      const user = userEvent.setup();
      render(<AuthPage />);
      
      expect(screen.getByText('Welcome back!')).toBeInTheDocument();
      
      const switchButton = screen.getByRole('button', { name: /sign up/i });
      await user.click(switchButton);
      
      expect(screen.getByText('Join us today!')).toBeInTheDocument();
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    });

    test('switches from register to login mode', async () => {
      const user = userEvent.setup();
      render(<AuthPage mode="register" />);
      
      expect(screen.getByText('Join us today!')).toBeInTheDocument();
      
      const switchButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(switchButton);
      
      expect(screen.getByText('Welcome back!')).toBeInTheDocument();
      expect(screen.queryByLabelText(/username/i)).not.toBeInTheDocument();
    });
  });
});
