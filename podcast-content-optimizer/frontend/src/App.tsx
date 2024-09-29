import React from 'react';
import { AppQueryProvider } from './contexts/AppContext';
import MainContent from './components/MainContent';

const App: React.FC = () => {
  return (
    <AppQueryProvider>
      <MainContent />
    </AppQueryProvider>
  );
};

export default App;