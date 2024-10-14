import React, { createContext, useState, useContext, useEffect, useCallback, useMemo, useRef } from 'react';
import { getProcessedPodcasts } from '../firebase';
import {
  JobStatus,
  fetchEpisodes as apiFetchEpisodes,
  fetchJobStatuses as apiFetchJobStatuses,
  enableAutoProcessing,
  savePodcastInfo,
  processEpisode as apiProcessEpisode,
  fetchCurrentJobs
} from '../api';

interface PodcastInfo {
  name: string;
  imageUrl: string;
}

interface JobInfo {
  podcastName: string;
  episodeTitle: string;
  rssUrl: string;
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
  autoPodcasts: string[];
  setAutoPodcasts: React.Dispatch<React.SetStateAction<string[]>>;
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
  handleEnableAutoProcessing: (podcast: SearchResult) => Promise<void>;
  error: string;
  setError: React.Dispatch<React.SetStateAction<string>>;
  fetchJobStatuses: () => Promise<void>;
  isLoading: boolean;
  fetchAllData: () => Promise<void>;
}

// Update the CurrentJob interface
interface CurrentJob {
  job_id: string;
  status: 'queued' | 'in_progress' | 'completed' | 'failed';
  podcast_name: string;
  episode_title: string;
  rss_url: string;
}

const PodcastContext = createContext<PodcastContextType | undefined>(undefined);

export const PodcastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [podcastInfo, setPodcastInfo] = useState<Record<string, PodcastInfo>>({});
  const [processedPodcasts, setProcessedPodcasts] = useState<Record<string, any[]>>({});
  const [autoPodcasts, setAutoPodcasts] = useState<string[]>([]);
  const [currentJobs, setCurrentJobs] = useState<CurrentJob[]>([]);
  const [jobStatuses, setJobStatuses] = useState<Record<string, JobStatus>>({});
  const [jobInfos, setJobInfos] = useState<Record<string, JobInfo>>({});
  const [isLoadingEpisodes, setIsLoadingEpisodes] = useState(false);
  const [isProcessingEpisode, setIsProcessingEpisode] = useState(false);
  const [episodes, setEpisodes] = useState<Record<string, Episode[]>>({});
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const initialFetchMade = useRef(false);

  const fetchAllData = useCallback(async (forceRefresh = false) => {
    if (!forceRefresh && initialFetchMade.current) {
      console.log('Skipping fetchAllData - already fetched and not forced');
      return;
    }

    console.log('Fetching all data...');
    setIsLoading(true);
    try {
      const [podcastData, jobs] = await Promise.all([
        getProcessedPodcasts(forceRefresh),
        fetchCurrentJobs()
      ]);
      console.log('Data fetched successfully');
      setProcessedPodcasts(podcastData.processed);
      setAutoPodcasts(podcastData.autoProcessed);
      setPodcastInfo(podcastData.podcastInfo);
      setCurrentJobs(jobs);

      const newJobInfos: Record<string, JobInfo> = {};
      jobs.forEach(job => {
        newJobInfos[job.job_id] = {
          podcastName: podcastData.podcastInfo[job.rss_url]?.name || job.podcast_name,
          episodeTitle: job.episode_title,
          rssUrl: job.rss_url
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
      setError('Failed to fetch podcast data. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllData(true);
  }, [fetchAllData]);

  const fetchEpisodes = useCallback(async (rssUrl: string) => {
    if (episodes[rssUrl]) return;
    setIsLoadingEpisodes(true);
    try {
      const fetchedEpisodes = await apiFetchEpisodes(rssUrl);
      setEpisodes(prev => ({ ...prev, [rssUrl]: fetchedEpisodes }));
    } catch (error) {
      console.error('Error fetching episodes:', error);
      setError('Failed to fetch episodes. Please try again.');
    } finally {
      setIsLoadingEpisodes(false);
    }
  }, [episodes, setError]);

  const fetchJobStatuses = async () => {
    const jobIds = [...currentJobs.map(job => job.job_id)].filter(Boolean) as string[];

    if (jobIds.length === 0) return;

    try {
      const data = await apiFetchJobStatuses(jobIds);
      setJobStatuses(prevStatuses => ({
        ...prevStatuses,
        ...data
      }));

      // Check for completed or failed jobs
      Object.entries(data).forEach(([jobId, status]) => {
        if (status.status === 'completed' || status.status === 'failed') {
          setCurrentJobs(prevJobs => prevJobs.filter(job => job.job_id !== jobId));
        }
      });

      if (Object.values(data).some(status => status.status === 'completed' || status.status === 'failed')) {
        const { processed, autoProcessed, podcastInfo: newPodcastInfo } = await getProcessedPodcasts();
        setProcessedPodcasts(processed);
        setAutoPodcasts(autoProcessed);
        setPodcastInfo(newPodcastInfo);
      }
    } catch (error) {
      console.error('Error fetching job statuses:', error);
    }
  };

  const handleProcessEpisode = async (rssUrl: string, episodeIndex: number) => {
    setIsProcessingEpisode(true);
    setError('');
    try {
      const data = await apiProcessEpisode(rssUrl, episodeIndex);
      const newJob: CurrentJob = {
        job_id: data.job_id,
        status: 'queued',
        podcast_name: podcastInfo[rssUrl]?.name || 'Unknown Podcast',
        episode_title: episodes[rssUrl][episodeIndex].title,
        rss_url: rssUrl
      };
      setCurrentJobs(prev => [...prev, newJob]);
      setJobInfos(prev => ({
        ...prev,
        [data.job_id]: {
          podcastName: newJob.podcast_name,
          episodeTitle: newJob.episode_title,
          rssUrl: newJob.rss_url
        }
      }));
    } catch (error) {
      console.error('Error processing episode:', error);
      setError(error instanceof Error ? error.message : 'Failed to process episode. Please try again.');
    } finally {
      setIsProcessingEpisode(false);
    }
  };

  const handleSelectPodcast = async (rssUrl: string) => {
    // Implement the logic here
  };

  const handleDeleteJob = async (jobId: string) => {
    // Implement the logic here
  };

  const handleDeletePodcast = async (podcastTitle: string, episodeTitle: string) => {
    // Implement the logic here
  };

  const handleEnableAutoProcessing = async (podcast: SearchResult) => {
    try {
      await enableAutoProcessing(podcast.rssUrl);
      await savePodcastInfo(podcast);

      setAutoPodcasts(prev => [...prev, podcast.rssUrl]);
      setPodcastInfo(prev => ({
        ...prev,
        [podcast.rssUrl]: { name: podcast.name, imageUrl: podcast.imageUrl }
      }));

      // Optionally, you can set a success message here
      // setNotification('Auto-processing enabled for this podcast.');
    } catch (error) {
      console.error('Error enabling auto-processing:', error);
      setError(error instanceof Error ? error.message : 'Failed to enable auto-processing. Please try again.');
    }
  };

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
    fetchAllData
  }), [
    podcastInfo, processedPodcasts, autoPodcasts, currentJobs, jobStatuses, jobInfos,
    isLoadingEpisodes, isProcessingEpisode, episodes, error, isLoading,
    fetchEpisodes, handleProcessEpisode, handleSelectPodcast, handleDeleteJob,
    handleDeletePodcast, handleEnableAutoProcessing, fetchJobStatuses, fetchAllData
  ]);

  return (
    <PodcastContext.Provider value={contextValue}>
      {children}
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
