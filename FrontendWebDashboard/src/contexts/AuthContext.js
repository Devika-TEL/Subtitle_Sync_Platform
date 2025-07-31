import React, { createContext, useContext, useState, useEffect } from 'react';
import { authenticateUser, registerUser } from '../services/api';

const AuthContext = createContext();

// PUBLIC_INTERFACE
/**
 * Custom hook to use authentication context
 * @returns {Object} - Authentication context value
 */
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// PUBLIC_INTERFACE
/**
 * AuthProvider component that manages authentication state
 * Provides authentication context to child components
 */
export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Check for existing authentication on mount
  useEffect(() => {
    checkAuthStatus();
  }, []);

  // PUBLIC_INTERFACE
  /**
   * Check if user is authenticated by validating stored token
   */
  const checkAuthStatus = async () => {
    try {
      const token = localStorage.getItem('authToken');
      if (token) {
        // In a real app, you would verify the token with the backend
        // For now, we'll assume the token is valid if it exists
        setUser({ 
          token, 
          username: localStorage.getItem('username') || 'user',
          role: localStorage.getItem('userRole') || 'user'
        });
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      localStorage.removeItem('authToken');
      localStorage.removeItem('username');
      localStorage.removeItem('userRole');
    } finally {
      setLoading(false);
    }
  };

  // PUBLIC_INTERFACE
  /**
   * Login user with email and password
   * @param {string} email - User email
   * @param {string} password - User password
   * @returns {Promise} - Login result
   */
  const login = async (email, password) => {
    try {
      setLoading(true);
      setError(null);
      
      const result = await authenticateUser(email, password);
      
      // Store authentication data
      localStorage.setItem('authToken', result.token || 'mock-token');
      localStorage.setItem('username', result.username || email);
      localStorage.setItem('userRole', result.role || 'user');
      
      setUser({
        token: result.token || 'mock-token',
        username: result.username || email,
        email: email,
        role: result.role || 'user',
        ...result
      });
      
      return result;
    } catch (error) {
      setError(error.message || 'Login failed');
      throw error;
    } finally {
      setLoading(false);
    }
  };

  // PUBLIC_INTERFACE
  /**
   * Register new user
   * @param {Object} userData - User registration data
   * @returns {Promise} - Registration result
   */
  const register = async (userData) => {
    try {
      setLoading(true);
      setError(null);
      
      const result = await registerUser(userData);
      
      // Auto-login after successful registration
      if (result.token) {
        localStorage.setItem('authToken', result.token);
        localStorage.setItem('username', result.username);
        localStorage.setItem('userRole', result.role || 'user');
        
        setUser({
          token: result.token,
          username: result.username,
          email: userData.email,
          role: result.role || 'user',
          ...result
        });
      }
      
      return result;
    } catch (error) {
      setError(error.message || 'Registration failed');
      throw error;
    } finally {
      setLoading(false);
    }
  };

  // PUBLIC_INTERFACE
  /**
   * Logout current user
   */
  const logout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('username');
    localStorage.removeItem('userRole');
    setUser(null);
    setError(null);
  };

  // PUBLIC_INTERFACE
  /**
   * Update user profile
   * @param {Object} updates - User profile updates
   */
  const updateUser = (updates) => {
    setUser(prevUser => ({
      ...prevUser,
      ...updates
    }));
    
    // Update localStorage if username or role changed
    if (updates.username) {
      localStorage.setItem('username', updates.username);
    }
    if (updates.role) {
      localStorage.setItem('userRole', updates.role);
    }
  };

  const value = {
    user,
    loading,
    error,
    login,
    register,
    logout,
    updateUser,
    isAuthenticated: !!user,
    isAdmin: user?.role === 'admin'
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;
