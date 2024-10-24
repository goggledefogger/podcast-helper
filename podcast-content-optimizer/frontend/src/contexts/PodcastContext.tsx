import React, { createContext, useState, useContext, useEffect, useCallback, useMemo, useRef } from 'react';
import { getProcessedPodcasts, AutoProcessedPodcast } from '../firebase';
import {
  JobStatus,
  fetchEpisodes as apiFetchEpisodes,
  fetchJobStatuses as apiFetchJobStatuses,
  enableAutoProcessing,
  processEpisode as apiProcessEpisode,
  fetchCurrentJobs,
  CurrentJob as ApiCurrentJob,
  deleteJob,
  deleteProcessedPodcast,
  deleteAutoProcessedPodcast as apiDeleteAutoProcessedPodcast // Add this line
} from '../api';
import Notification from '../components/Notification';

interface PodcastInfo {
  name: string;
  imageUrl: string;
}

interface JobInfo {
  podcastName: string;
  episodeTitle: string;
  rssUrl: string;
  imageUrl: string;
}

interface Episode {
  number: number;
  title: string;
  published: string;
  duration: number;
}

interface SearchResult {
  uuid: string;
  name: string;
  description: string;
  imageUrl: string;
  rssUrl: string;
}

interface PodcastContextType {
  podcastInfo: Record<string, PodcastInfo>;
  setPodcastInfo: React.Dispatch<React.SetStateAction<Record<string, PodcastInfo>>>;
  processedPodcasts: Record<string, any[]>;
  setProcessedPodcasts: React.Dispatch<React.SetStateAction<Record<string, any[]>>>;
  autoPodcasts: AutoProcessedPodcast[];
  setAutoPodcasts: React.Dispatch<React.SetStateAction<AutoProcessedPodcast[]>>;
  currentJobs: CurrentJob[];
  setCurrentJobs: React.Dispatch<React.SetStateAction<CurrentJob[]>>;
  jobStatuses: Record<string, JobStatus>;
  setJobStatuses: React.Dispatch<React.SetStateAction<Record<string, JobStatus>>>;
  jobInfos: Record<string, JobInfo>;
  setJobInfos: React.Dispatch<React.SetStateAction<Record<string, JobInfo>>>;
  isLoadingEpisodes: boolean;
  setIsLoadingEpisodes: React.Dispatch<React.SetStateAction<boolean>>;
  isProcessingEpisode: boolean;
  setIsProcessingEpisode: React.Dispatch<React.SetStateAction<boolean>>;
  episodes: Record<string, Episode[]>;
  setEpisodes: React.Dispatch<React.SetStateAction<Record<string, Episode[]>>>;
  fetchEpisodes: (rssUrl: string) => Promise<void>;
  handleProcessEpisode: (rssUrl: string, episodeIndex: number) => Promise<void>;
  handleSelectPodcast: (rssUrl: string) => Promise<void>;
  handleDeleteJob: (jobId: string) => Promise<void>;
  handleDeletePodcast: (podcastTitle: string, episodeTitle: string) => Promise<void>;
  handleEnableAutoProcessing: (podcast: SearchResult) => Promise<string>;
  error: string;
  setError: React.Dispatch<React.SetStateAction<string>>;
  fetchJobStatuses: () => Promise<void>;
  isLoading: boolean;
  fetchAllData: () => Promise<void>;
  errorMessage: string | null;
  setErrorMessage: React.Dispatch<React.SetStateAction<string | null>>;
  successMessage: string | null;
  setSuccessMessage: React.Dispatch<React.SetStateAction<string | null>>;
  deleteAutoProcessedPodcast: (rssUrl: string) => Promise<void>;
}

interface CurrentJob extends ApiCurrentJob {
  podcast_name: string;
  episode_title: string;
  rss_url: string;
  image_url: string;
}

const PodcastContext = createContext<PodcastContextType | undefined>(undefined);

export const PodcastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [podcastInfo, setPodcastInfo] = useState<Record<string, PodcastInfo>>({});
  const [processedPodcasts, setProcessedPodcasts] = useState<Record<string, any[]>>({});
  const [autoPodcasts, setAutoPodcasts] = useState<AutoProcessedPodcast[]>([]);
  const [currentJobs, setCurrentJobs] = useState<CurrentJob[]>([]);
  const [jobStatuses, setJobStatuses] = useState<Record<string, JobStatus>>({});
  const [jobInfos, setJobInfos] = useState<Record<string, JobInfo>>({});
  const [isLoadingEpisodes, setIsLoadingEpisodes] = useState(false);
  const [isProcessingEpisode, setIsProcessingEpisode] = useState(false);
  const [episodes, setEpisodes] = useState<Record<string, Episode[]>>({});
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const initialFetchMade = useRef(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fetchAllData = useCallback(async (forceRefresh = false) => {
    if (!forceRefresh && initialFetchMade.current) {
      console.log('Skipping fetchAllData - already fetched and not forced');
      return;
    }

    console.log('Fetching all data...');
    setIsLoading(true);
    setErrorMessage(null);  // Clear any previous error messages
    try {
      const [podcastData, jobs] = await Promise.all([
        getProcessedPodcasts(forceRefresh),
        fetchCurrentJobs()
      ]);

      setProcessedPodcasts(podcastData.processed);
      setAutoPodcasts(podcastData.autoProcessed);
      setPodcastInfo(podcastData.podcastInfo);

      setCurrentJobs(jobs as CurrentJob[]);

      const newJobInfos: Record<string, JobInfo> = {};
      jobs.forEach(job => {
        const podcastInfoData = podcastData.podcastInfo[job.rss_url] || {};
        newJobInfos[job.job_id] = {
          podcastName: job.podcast_name || podcastInfoData.name || 'Unknown Podcast',
          episodeTitle: job.episode_title || 'Unknown Episode',
          rssUrl: job.rss_url || '',
          imageUrl: job.image_url || podcastInfoData.imageUrl || ''
        };
      });
      setJobInfos(newJobInfos);

      if (jobs.length > 0) {
        const statuses = await apiFetchJobStatuses(jobs.map(job => job.job_id));
        setJobStatuses(statuses);
      }

      initialFetchMade.current = true;
    } catch (error) {
      console.error('Error fetching podcast data:', error);
      setErrorMessage('Unable to load podcast data. Please check your internet connection and try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  const fetchEpisodes = useCallback(async (rssUrl: string) => {
    if (episodes[rssUrl]) return;
    try {
      const fetchedEpisodes = await apiFetchEpisodes(rssUrl);
      setEpisodes(prev => ({ ...prev, [rssUrl]: fetchedEpisodes }));
    } catch (error) {
      console.error('Error fetching episodes:', error);
      setErrorMessage('Unable to fetch episodes. The server might be down. Please try again later.');
    }
  }, [episodes, setErrorMessage]);

  const fetchJobStatuses = useCallback(async () => {
    if (currentJobs.length === 0) return;

    try {
      const statuses = await apiFetchJobStatuses(currentJobs.map(job => job.job_id));
      setJobStatuses(prevStatuses => ({
        ...prevStatuses,
        ...statuses
      }));

      // Check for completed jobs and update processed podcasts
      Object.entries(statuses).forEach(([jobId, status]) => {
        if (status.status === 'completed') {
          const completedJob = currentJobs.find(job => job.job_id === jobId);
          if (completedJob) {
            fetchAllData(true); // Force refresh of all data, including processed podcasts
            setCurrentJobs(prevJobs => prevJobs.filter(job => job.job_id !== jobId));
          }
        }
      });
    } catch (error) {
      console.error('Error fetching job statuses:', error);
    }
  }, [currentJobs, fetchAllData]);

  // Add this new effect to poll for status updates more frequently
  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    if (currentJobs.length > 0) {
      intervalId = setInterval(fetchJobStatuses, 5000); // Poll every 5 seconds
    }

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [currentJobs, fetchJobStatuses]);

  const handleProcessEpisode = useCallback(async (rssUrl: string, episodeIndex: number) => {
    setIsProcessingEpisode(true);
    setErrorMessage(null);
    try {
      const data = await apiProcessEpisode(rssUrl, episodeIndex);
      const podcastInfoData = podcastInfo[rssUrl] || {};
      const newJob: CurrentJob = {
        job_id: data.job_id,
        status: 'queued',
        podcast_name: podcastInfoData.name || 'Unknown Podcast',
        episode_title: episodes[rssUrl][episodeIndex].title,
        rss_url: rssUrl,  // Ensure this is set correctly
        image_url: podcastInfoData.imageUrl || ''
      };
      setCurrentJobs(prev => [...prev, newJob]);

      // Immediately set a temporary job status
      setJobStatuses(prev => ({
        ...prev,
        [data.job_id]: {
          status: 'queued',
          current_stage: 'INITIALIZATION',
          progress: 0,
          message: 'Job queued, waiting to start...',
          timestamp: Date.now() / 1000
        }
      }));

      setJobInfos(prev => ({
        ...prev,
        [data.job_id]: {
          podcastName: newJob.podcast_name,
          episodeTitle: newJob.episode_title,
          rssUrl: rssUrl,  // Ensure this is set correctly
          imageUrl: podcastInfoData.imageUrl || ''
        }
      }));

      // Fetch the actual job status
      fetchJobStatuses();
      setSuccessMessage('Episode processing started successfully.');
    } catch (error) {
      console.error('Error processing episode:', error);
      setErrorMessage(error instanceof Error ? error.message : 'Failed to start episode processing. Please try again.');
    } finally {
      setIsProcessingEpisode(false);
    }
  }, [podcastInfo, episodes, setCurrentJobs, setJobInfos, setJobStatuses, setIsProcessingEpisode, fetchJobStatuses]);

  const handleSelectPodcast = useCallback(async (rssUrl: string) => {
    // Implement the logic here
  }, []);

  const handleDeleteJob = useCallback(async (jobId: string) => {
    try {
      await deleteJob(jobId);
      setCurrentJobs(prevJobs => prevJobs.filter(job => job.job_id !== jobId));
      setJobStatuses(prevStatuses => {
        const newStatuses = { ...prevStatuses };
        delete newStatuses[jobId];
        return newStatuses;
      });
      setJobInfos(prevInfos => {
        const newInfos = { ...prevInfos };
        delete newInfos[jobId];
        return newInfos;
      });
    } catch (error) {
      console.error('Error deleting job:', error);
      setError(error instanceof Error ? error.message : 'Failed to delete job');
    }
  }, [setCurrentJobs, setJobStatuses, setJobInfos, setError]);

  const handleDeletePodcast = useCallback(async (podcastTitle: string, episodeTitle: string) => {
    try {
      await deleteProcessedPodcast(podcastTitle, episodeTitle);
      setProcessedPodcasts(prevPodcasts => {
        const newPodcasts = { ...prevPodcasts };
        Object.keys(newPodcasts).forEach(rssUrl => {
          newPodcasts[rssUrl] = newPodcasts[rssUrl].filter(
            podcast => !(podcast.podcast_title === podcastTitle && podcast.episode_title === episodeTitle)
          );
          if (newPodcasts[rssUrl].length === 0) {
            delete newPodcasts[rssUrl];
          }
        });
        return newPodcasts;
      });
      setSuccessMessage('Episode deleted successfully');
    } catch (error) {
      console.error('Error deleting podcast:', error);
      setErrorMessage(error instanceof Error ? error.message : 'Failed to delete podcast. Please try again.');
    }
  }, [setProcessedPodcasts]);

  const handleEnableAutoProcessing = useCallback(async (podcast: SearchResult) => {
    try {
      const response = await enableAutoProcessing(podcast.rssUrl);
      const newAutoPodcast: AutoProcessedPodcast = {
        rss_url: podcast.rssUrl,
        enabled_at: response.enabled_at
      };

      setAutoPodcasts(prev => {
        const updatedPodcasts = prev.filter(p => p.rss_url !== podcast.rssUrl);
        return [...updatedPodcasts, newAutoPodcast];
      });
      setPodcastInfo(prev => ({
        ...prev,
        [podcast.rssUrl]: { name: podcast.name, imageUrl: podcast.imageUrl }
      }));

      setSuccessMessage(`Auto-processing enabled for ${podcast.name}`);
      return `Auto-processing enabled for ${podcast.name}`;
    } catch (error) {
      console.error('Error enabling auto-processing:', error);
      setErrorMessage(error instanceof Error ? error.message : 'Failed to enable auto-processing. Please try again.');
      throw error;
    }
  }, [setAutoPodcasts, setPodcastInfo]);

  const deleteAutoProcessedPodcast = useCallback(async (rssUrl: string) => {
    try {
      await apiDeleteAutoProcessedPodcast(rssUrl);
      setAutoPodcasts(prevAutoPodcasts => prevAutoPodcasts.filter(podcast => podcast.rss_url !== rssUrl));
      setSuccessMessage('Auto-processed podcast deleted successfully');
    } catch (error) {
      console.error('Error deleting auto-processed podcast:', error);
      setErrorMessage('Failed to delete auto-processed podcast. Please try again.');
    }
  }, []);

  const contextValue = useMemo(() => ({
    podcastInfo,
    setPodcastInfo,
    processedPodcasts,
    setProcessedPodcasts,
    autoPodcasts,
    setAutoPodcasts,
    currentJobs,
    setCurrentJobs,
    jobStatuses,
    setJobStatuses,
    jobInfos,
    setJobInfos,
    isLoadingEpisodes,
    setIsLoadingEpisodes,
    isProcessingEpisode,
    setIsProcessingEpisode,
    episodes,
    setEpisodes,
    fetchEpisodes,
    handleProcessEpisode,
    handleSelectPodcast,
    handleDeleteJob,
    handleDeletePodcast,
    handleEnableAutoProcessing,
    error,
    setError,
    fetchJobStatuses,
    isLoading,
    fetchAllData,
    errorMessage,
    setErrorMessage,
    successMessage,
    setSuccessMessage,
    deleteAutoProcessedPodcast
  }), [
    podcastInfo, processedPodcasts, autoPodcasts, currentJobs, jobStatuses, jobInfos,
    isLoadingEpisodes, isProcessingEpisode, episodes, error, isLoading,
    fetchEpisodes, handleProcessEpisode, handleSelectPodcast, handleDeleteJob,
    handleDeletePodcast, handleEnableAutoProcessing, fetchJobStatuses, fetchAllData,
    errorMessage, successMessage, deleteAutoProcessedPodcast
  ]);

  return (
    <PodcastContext.Provider value={contextValue}>
      {children}
      {errorMessage && (
        <Notification
          message={errorMessage}
          type="error"
          onClose={() => setErrorMessage(null)}
        />
      )}
      {successMessage && (
        <Notification
          message={successMessage}
          type="success"
          onClose={() => setSuccessMessage(null)}
        />
      )}
    </PodcastContext.Provider>
  );
};

export const usePodcastContext = () => {
  const context = useContext(PodcastContext);
  if (context === undefined) {
    throw new Error('usePodcastContext must be used within a PodcastProvider');
  }
  return context;
};
