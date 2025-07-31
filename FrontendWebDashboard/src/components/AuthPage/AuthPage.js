import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import './AuthPage.css';

// PUBLIC_INTERFACE
/**
 * Unified authentication page component for login and registration
 * Provides responsive design and comprehensive form validation
 */
const AuthPage = ({ mode = 'login' }) => {
  const [currentMode, setCurrentMode] = useState(mode);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    username: '',
    acceptTerms: false
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  
  const { login, register } = useAuth();

  // PUBLIC_INTERFACE
  /**
   * Handle form input changes
   * @param {Event} e - Input change event
   */
  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    
    // Clear error when user starts typing
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: ''
      }));
    }
  };

  // PUBLIC_INTERFACE
  /**
   * Validate form data
   * @returns {boolean} - Whether form is valid
   */
  const validateForm = () => {
    const newErrors = {};

    // Email validation
    if (!formData.email) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Please enter a valid email address';
    }

    // Password validation
    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters';
    }

    // Registration-specific validation
    if (currentMode === 'register') {
      if (!formData.username) {
        newErrors.username = 'Username is required';
      } else if (formData.username.length < 3) {
        newErrors.username = 'Username must be at least 3 characters';
      }

      if (!formData.confirmPassword) {
        newErrors.confirmPassword = 'Please confirm your password';
      } else if (formData.password !== formData.confirmPassword) {
        newErrors.confirmPassword = 'Passwords do not match';
      }

      if (!formData.acceptTerms) {
        newErrors.acceptTerms = 'You must accept the terms and conditions';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // PUBLIC_INTERFACE
  /**
   * Handle form submission
   * @param {Event} e - Form submit event
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setLoading(true);

    try {
      if (currentMode === 'login') {
        await login(formData.email, formData.password);
        window.showNotification?.({
          type: 'success',
          message: 'Successfully logged in!',
          duration: 3000
        });
      } else {
        await register({
          username: formData.username,
          email: formData.email,
          password: formData.password
        });
        window.showNotification?.({
          type: 'success',
          message: 'Account created successfully!',
          duration: 3000
        });
      }
    } catch (error) {
      window.showNotification?.({
        type: 'error',
        message: error.message || `${currentMode === 'login' ? 'Login' : 'Registration'} failed`,
        duration: 5000
      });
    } finally {
      setLoading(false);
    }
  };

  // PUBLIC_INTERFACE
  /**
   * Switch between login and registration modes
   */
  const switchMode = () => {
    setCurrentMode(prev => prev === 'login' ? 'register' : 'login');
    setErrors({});
    setFormData({
      email: formData.email, // Keep email when switching
      password: '',
      confirmPassword: '',
      username: '',
      acceptTerms: false
    });
  };

  return (
    <div className="auth-page">
      <div className="auth-background">
        <div className="auth-pattern"></div>
      </div>
      
      <div className="auth-container">
        <div className="auth-card">
          <div className="auth-header">
            <div className="auth-logo">
              <div className="logo-icon">🎬</div>
              <h1 className="logo-text">SubtitleSync</h1>
            </div>
            <p className="auth-tagline">
              {currentMode === 'login' ? 'Welcome back!' : 'Join us today!'}
            </p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            {currentMode === 'register' && (
              <div className="form-group">
                <label htmlFor="username" className="form-label">
                  Username
                </label>
                <input
                  type="text"
                  id="username"
                  name="username"
                  value={formData.username}
                  onChange={handleInputChange}
                  className={`form-input ${errors.username ? 'error' : ''}`}
                  placeholder="Enter your username"
                  disabled={loading}
                />
                {errors.username && (
                  <span className="form-error">{errors.username}</span>
                )}
              </div>
            )}

            <div className="form-group">
              <label htmlFor="email" className="form-label">
                Email Address
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                className={`form-input ${errors.email ? 'error' : ''}`}
                placeholder="Enter your email"
                disabled={loading}
                autoComplete="email"
              />
              {errors.email && (
                <span className="form-error">{errors.email}</span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="password" className="form-label">
                Password
              </label>
              <input
                type="password"
                id="password"
                name="password"
                value={formData.password}
                onChange={handleInputChange}
                className={`form-input ${errors.password ? 'error' : ''}`}
                placeholder="Enter your password"
                disabled={loading}
                autoComplete={currentMode === 'login' ? 'current-password' : 'new-password'}
              />
              {errors.password && (
                <span className="form-error">{errors.password}</span>
              )}
            </div>

            {currentMode === 'register' && (
              <div className="form-group">
                <label htmlFor="confirmPassword" className="form-label">
                  Confirm Password
                </label>
                <input
                  type="password"
                  id="confirmPassword"
                  name="confirmPassword"
                  value={formData.confirmPassword}
                  onChange={handleInputChange}
                  className={`form-input ${errors.confirmPassword ? 'error' : ''}`}
                  placeholder="Confirm your password"
                  disabled={loading}
                  autoComplete="new-password"
                />
                {errors.confirmPassword && (
                  <span className="form-error">{errors.confirmPassword}</span>
                )}
              </div>
            )}

            {currentMode === 'register' && (
              <div className="form-group checkbox-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    name="acceptTerms"
                    checked={formData.acceptTerms}
                    onChange={handleInputChange}
                    className="form-checkbox"
                    disabled={loading}
                  />
                  <span className="checkbox-text">
                    I agree to the <a href="/terms" className="link">Terms of Service</a> and{' '}
                    <a href="/privacy" className="link">Privacy Policy</a>
                  </span>
                </label>
                {errors.acceptTerms && (
                  <span className="form-error">{errors.acceptTerms}</span>
                )}
              </div>
            )}

            <button
              type="submit"
              className="auth-submit-btn"
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="loading-spinner"></span>
                  {currentMode === 'login' ? 'Signing In...' : 'Creating Account...'}
                </>
              ) : (
                <>
                  <span>{currentMode === 'login' ? '🔑' : '🚀'}</span>
                  {currentMode === 'login' ? 'Sign In' : 'Create Account'}
                </>
              )}
            </button>
          </form>

          <div className="auth-footer">
            <p className="auth-switch-text">
              {currentMode === 'login' ? "Don't have an account?" : 'Already have an account?'}
              <button
                type="button"
                className="auth-switch-btn"
                onClick={switchMode}
                disabled={loading}
              >
                {currentMode === 'login' ? 'Sign Up' : 'Sign In'}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthPage;
