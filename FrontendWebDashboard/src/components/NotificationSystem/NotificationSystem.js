import React, { useState, useEffect, useCallback } from 'react';
import './NotificationSystem.css';

// PUBLIC_INTERFACE
/**
 * Enhanced notification system with multiple types, positioning, and auto-dismiss
 * Supports success, error, warning, info notifications with customizable duration
 */
const NotificationSystem = () => {
  const [notifications, setNotifications] = useState([]);

  // PUBLIC_INTERFACE
  /**
   * Add a new notification
   * @param {Object} notification - Notification object
   */
  const addNotification = useCallback((notification) => {
    const id = Date.now() + Math.random();
    const newNotification = {
      id,
      type: 'info',
      duration: 5000,
      ...notification,
      timestamp: new Date()
    };

    setNotifications(prev => [...prev, newNotification]);

    // Auto-dismiss after duration
    if (newNotification.duration > 0) {
      setTimeout(() => {
        removeNotification(id);
      }, newNotification.duration);
    }
  }, []);

  // PUBLIC_INTERFACE
  /**
   * Remove notification by ID
   * @param {string|number} id - Notification ID
   */
  const removeNotification = useCallback((id) => {
    setNotifications(prev => prev.filter(notification => notification.id !== id));
  }, []);

  // PUBLIC_INTERFACE
  /**
   * Clear all notifications
   */
  const clearAll = useCallback(() => {
    setNotifications([]);
  }, []);

  // Expose methods globally for easy access
  useEffect(() => {
    window.showNotification = addNotification;
    window.clearNotifications = clearAll;
    
    return () => {
      delete window.showNotification;
      delete window.clearNotifications;
    };
  }, [addNotification, clearAll]);

  return (
    <div className="notification-system">
      {notifications.map((notification) => (
        <NotificationItem
          key={notification.id}
          notification={notification}
          onClose={() => removeNotification(notification.id)}
        />
      ))}
    </div>
  );
};

// Individual notification component
const NotificationItem = ({ notification, onClose }) => {
  const [isVisible, setIsVisible] = useState(false);
  const [isRemoving, setIsRemoving] = useState(false);

  useEffect(() => {
    // Trigger entrance animation
    const timer = setTimeout(() => setIsVisible(true), 10);
    return () => clearTimeout(timer);
  }, []);

  const handleClose = () => {
    setIsRemoving(true);
    setTimeout(onClose, 300); // Match CSS animation duration
  };

  const getIcon = () => {
    switch (notification.type) {
      case 'success': return '✅';
      case 'error': return '❌';
      case 'warning': return '⚠️';
      case 'info': return 'ℹ️';
      default: return 'ℹ️';
    }
  };

  return (
    <div 
      className={`notification-item ${notification.type} ${isVisible ? 'visible' : ''} ${isRemoving ? 'removing' : ''}`}
    >
      <div className="notification-content">
        <div className="notification-icon">
          {getIcon()}
        </div>
        <div className="notification-body">
          {notification.title && (
            <div className="notification-title">{notification.title}</div>
          )}
          <div className="notification-message">{notification.message}</div>
          {notification.details && (
            <div className="notification-details">{notification.details}</div>
          )}
        </div>
        <button 
          className="notification-close"
          onClick={handleClose}
          aria-label="Close notification"
        >
          ×
        </button>
      </div>
      {notification.progress !== undefined && (
        <div className="notification-progress">
          <div 
            className="notification-progress-bar"
            style={{ width: `${notification.progress}%` }}
          />
        </div>
      )}
    </div>
  );
};

export default NotificationSystem;
