import React, { createContext, useContext, useCallback } from 'react';
import { useQuery, QueryClient, QueryClientProvider } from 'react-query';
import { ProcessedPodcast, getDbJson } from '../firebase';
import { fetchCurrentJobs, JobStatus } from '../api';

const queryClient = new QueryClient();

interface AppContextType {
  dbData: any;
  processedPodcasts: ProcessedPodcast[];
  currentJobs: { job_id: string; status: JobStatus }[];
  refreshData: () => void;
  isLoading: boolean;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { data: dbData, isLoading: isDbLoading, refetch: refetchDbData } = useQuery('dbJson', getDbJson, {
    staleTime: 300000, // 5 minutes
  });

  const { data: currentJobs = [], isLoading: isJobsLoading, refetch: refetchJobs } = useQuery('currentJobs', fetchCurrentJobs, {
    staleTime: 60000, // 1 minute
  });

  const processedPodcasts = dbData?.processed_podcasts || [];

  const refreshData = useCallback(() => {
    refetchDbData();
    refetchJobs();
  }, [refetchDbData, refetchJobs]);

  const isLoading = isDbLoading || isJobsLoading;

  return (
    <AppContext.Provider value={{
      dbData,
      processedPodcasts,
      currentJobs,
      refreshData,
      isLoading,
    }}>
      {children}
    </AppContext.Provider>
  );
};

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
};

export const AppQueryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <QueryClientProvider client={queryClient}>
    <AppProvider>{children}</AppProvider>
  </QueryClientProvider>
);