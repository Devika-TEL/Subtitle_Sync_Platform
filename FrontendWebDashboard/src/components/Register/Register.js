import React, { useState } from 'react';
import { registerUser } from '../../services/api';


// PUBLIC_INTERFACE
/**
 * Register component for user registration
 * @param {Object} props - Component props
 * @param {Function} props.onRegisterSuccess - Callback function called on successful registration
 * @param {Function} props.onSwitchToLogin - Callback function to switch to login view
 */
const Register = ({ onRegisterSuccess, onSwitchToLogin }) => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const validateForm = () => {
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return false;
    }
    // Password validation rules
    const password = formData.password;
    const validationErrors = [];
    
    if (password.length < 8) {
      validationErrors.push('Password must be at least 8 characters long');
    }
    if (!/[a-z]/.test(password)) {
      validationErrors.push('Password must contain lowercase letters');
    }
    if (!/[A-Z]/.test(password)) {
      validationErrors.push('Password must contain uppercase letters');
    }
    if (!/[0-9]/.test(password)) {
      validationErrors.push('Password must contain numbers');
    }
    if (!/[!@#$%^&*()_+\-=[\]{};:,.<>?]/.test(password)) {
      validationErrors.push('Password must contain special characters');
    }
    
    if (validationErrors.length > 0) {
      setError(validationErrors.join('\n'));
      return false;
    }
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!validateForm()) {
      return;
    }

    setLoading(true);

    try {
      // Remove confirmPassword before sending to API
      const { confirmPassword, ...registrationData } = formData;
      const result = await registerUser(registrationData);
      
      // Store the token and call the success callback
      localStorage.setItem('authToken', result.token);
      onRegisterSuccess(result.user);
    } catch (err) {
      const errorDetail = err.response?.data?.detail;
      if (typeof errorDetail === 'object' && errorDetail.issues) {
        // Show specific password validation issues
        setError(errorDetail.issues.join('\n'));
      } else if (errorDetail === "Username already exists") {
        setError('Username is already taken. Please choose another.');
      } else {
        setError(
          err.response?.data?.message || 
          errorDetail ||
          'Registration failed. Please try again.'
        );
      }
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const styles = {
    authContainer: {
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)',
      padding: '20px'
    },
    authForm: {
      background: 'white',
      padding: '2rem',
      borderRadius: '8px',
      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
      width: '100%',
      maxWidth: '400px'
    },
    heading: {
      margin: '0 0 1.5rem',
      color: '#1e3c72',
      textAlign: 'center',
      fontSize: '1.75rem'
    },
    input: {
      width: '100%',
      padding: '0.75rem',
      marginBottom: '1rem',
      border: '1px solid #ddd',
      borderRadius: '4px',
      fontSize: '1rem'
    },
    submitButton: {
      width: '100%',
      padding: '0.75rem',
      background: '#2a5298',
      color: 'white',
      border: 'none',
      borderRadius: '4px',
      fontSize: '1rem',
      cursor: 'pointer',
      transition: 'background-color 0.2s'
    },
    submitButtonDisabled: {
      background: '#94a3b8',
      cursor: 'not-allowed'
    },
    error: {
      background: '#fee2e2',
      color: '#dc2626',
      padding: '0.75rem',
      borderRadius: '4px',
      marginBottom: '1rem',
      textAlign: 'center'
    },
    footer: {
      marginTop: '1.5rem',
      textAlign: 'center',
      color: '#64748b'
    },
    linkButton: {
      background: 'none',
      border: 'none',
      color: '#2a5298',
      fontWeight: '500',
      cursor: 'pointer',
      padding: '0',
      fontSize: 'inherit'
    }
  };

  return (
    <div style={styles.authContainer}>
      <form style={styles.authForm} onSubmit={handleSubmit}>
        <h2 style={styles.heading}>Create Account</h2>
        
        {error && <div style={styles.error}>{error}</div>}
        
        <input
          type="text"
          name="name"
          placeholder="Full Name"
          value={formData.name}
          onChange={handleChange}
          required
          disabled={loading}
          style={styles.input}
        />
        
        <input
          type="email"
          name="email"
          placeholder="Email"
          value={formData.email}
          onChange={handleChange}
          required
          disabled={loading}
          style={styles.input}
        />
        
        <input
          type="password"
          name="password"
          placeholder="Password"
          value={formData.password}
          onChange={handleChange}
          required
          disabled={loading}
          minLength={6}
          style={styles.input}
        />
        
        <input
          type="password"
          name="confirmPassword"
          placeholder="Confirm Password"
          value={formData.confirmPassword}
          onChange={handleChange}
          required
          disabled={loading}
          minLength={6}
          style={styles.input}
        />
        
        <button 
          type="submit" 
          disabled={loading}
          style={{
            ...styles.submitButton,
            ...(loading ? styles.submitButtonDisabled : {})
          }}
        >
          {loading ? 'Creating Account...' : 'Sign Up'}
        </button>
        
        <div style={styles.footer}>
          <p>
            Already have an account?{' '}
            <button
              type="button"
              style={styles.linkButton}
              onClick={onSwitchToLogin}
              disabled={loading}
            >
              Log In
            </button>
          </p>
        </div>
      </form>
    </div>
  );
};

export default Register;
