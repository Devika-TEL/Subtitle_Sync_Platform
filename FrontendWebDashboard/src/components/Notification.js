import React, { useState, useEffect } from 'react';
import './Notification.css';

// PUBLIC_INTERFACE
/**
 * Notification component for displaying messages to users
 * @param {Object} props - Component props
 * @param {string} props.message - Notification message
 * @param {string} props.type - Notification type (success, error, warning, info)
 * @param {number} props.duration - Auto-dismiss duration in milliseconds
 * @param {Function} props.onClose - Callback when notification is closed
 */
const Notification = ({ message, type = 'info', duration = 5000, onClose }) => {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => {
        setIsVisible(false);
        setTimeout(onClose, 300); // Allow fade animation to complete
      }, duration);

      return () => clearTimeout(timer);
    }
  }, [duration, onClose]);

  const handleClose = () => {
    setIsVisible(false);
    setTimeout(onClose, 300);
  };

  if (!isVisible) return null;

  return (
    <div className={`notification notification-${type} ${isVisible ? 'show' : ''}`}>
      <div className="notification-content">
        <span className="notification-message">{message}</span>
        <button className="notification-close" onClick={handleClose} aria-label="Close notification">
          ×
        </button>
      </div>
    </div>
  );
};

export default Notification;
