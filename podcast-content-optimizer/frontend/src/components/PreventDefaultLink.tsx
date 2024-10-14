import React from 'react';

interface PreventDefaultLinkProps {
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
}

const PreventDefaultLink: React.FC<PreventDefaultLinkProps> = ({ children, onClick, className }) => {
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (onClick) onClick();
  };

  return (
    <button onClick={handleClick} className={className}>
      {children}
    </button>
  );
};

export default PreventDefaultLink;
