import React from 'react';
import './Notification.css';

interface NotificationProps {
  message: string;
  type: 'error' | 'success';
  onClose: () => void;
}

const Notification: React.FC<NotificationProps> = ({ message, type, onClose }) => {
  return (
    <div className={`notification ${type}`}>
      <p>{message}</p>
      <button onClick={onClose} className="close-notification">×</button>
    </div>
  );
};

export default Notification;
