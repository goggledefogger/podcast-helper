import React from 'react';
import './Loader.css';

interface LoaderProps {
  fullPage?: boolean;
}

const Loader: React.FC<LoaderProps> = ({ fullPage = false }) => {
  return (
    <div className={`loader ${fullPage ? 'full-page' : ''}`}>
      <div className="spinner"></div>
    </div>
  );
};

export default Loader;
