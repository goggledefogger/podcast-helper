import React, { useState, useEffect, useCallback } from 'react';
import Modal from 'react-modal';
import './App.css';
import ProcessingStatus from './components/ProcessingStatus';
import {
  fetchEpisodes,
  processEpisode,
  searchPodcasts,
  fetchCurrentJobs,
  deleteJob,
  fetchJobStatuses,
  deleteProcessedPodcast,
  JobStatus,
  enableAutoProcessing,
  savePodcastInfo,
  CurrentJob
} from './api';
import { ProcessedPodcast, getProcessedPodcasts, getFileUrl } from './firebase';
import PromptEditor from './components/PromptEditor';
import { API_BASE_URL } from './api';
import AutoProcessedPodcast from './components/AutoProcessedPodcast';
import { FaPodcast, FaChevronDown, FaChevronUp } from 'react-icons/fa';
import PreventDefaultLink from './components/PreventDefaultLink';

// Add this line at the top of your file, after the imports
Modal.setAppElement('#root');

interface Episode {
  number: number;
  title: string;
  published: string;
  duration: number;  // Duration in seconds
}

interface SearchResult {
  uuid: string;
  name: string;
  description: string;
  imageUrl: string;
  rssUrl: string;
}

const App: React.FC = () => {
  const [rssUrl, setRssUrl] = useState('');
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [processedPodcasts, setProcessedPodcasts] = useState<Record<string, ProcessedPodcast[]>>({});
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [currentJobs, setCurrentJobs] = useState<CurrentJob[]>([]);
  const [jobStatuses, setJobStatuses] = useState<Record<string, JobStatus>>({});
  const [currentJobInfo, setCurrentJobInfo] = useState<{ podcastName: string; episodeTitle: string; rssUrl: string } | null>(null);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [notification, setNotification] = useState<string | null>(null);
  const [autoPodcasts, setAutoPodcasts] = useState<string[]>([]);
  const [isDataLoaded, setIsDataLoaded] = useState(false);
  const [isLoadingEpisodes, setIsLoadingEpisodes] = useState(false);
  const [isProcessingEpisode, setIsProcessingEpisode] = useState(false);
  const [expandedPodcasts, setExpandedPodcasts] = useState<string[]>([]);
  const [podcastInfo, setPodcastInfo] = useState<Record<string, { name: string; imageUrl: string }>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedPodcast, setSelectedPodcast] = useState<SearchResult | null>(null);
  const [selectedEpisodeIndex, setSelectedEpisodeIndex] = useState<number | null>(null);

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null;
    if (savedTheme) {
      setTheme(savedTheme);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      setTheme('dark');
    }
  }, []);

  useEffect(() => {
    console.log('Theme changed:', theme);
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    console.log('Toggle theme called');
    setTheme(prevTheme => {
      const newTheme = prevTheme === 'light' ? 'dark' : 'light';
      console.log('New theme:', newTheme);
      return newTheme;
    });
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const { processed, autoProcessed, podcastInfo } = await getProcessedPodcasts();
        setProcessedPodcasts(processed);
        setAutoPodcasts(autoProcessed);
        setPodcastInfo(podcastInfo);
        console.log('Fetched podcastInfo:', podcastInfo); // Add this line for debugging
      } catch (error) {
        handleError(error as Error);
      } finally {
        setIsDataLoaded(true);
      }
    };

    fetchData();
    fetchCurrentJobs().then(setCurrentJobs).catch(handleError);
  }, []);

  const handleError = (error: Error) => {
    console.error('Error:', error);
    setError(error.message);
  };

  const fetchPodcastEpisodes = useCallback(async (url: string) => {
    setIsLoadingEpisodes(true);
    setError('');
    try {
      const data = await fetchEpisodes(url);
      setEpisodes(data);
    } catch (err) {
      handleError(err as Error);
    } finally {
      setIsLoadingEpisodes(false);
    }
  }, []);

  const handleProcessEpisode = async (rssUrl: string, episodeIndex: number) => {
    setError('');
    setIsProcessing(true);

    try {
      const data = await processEpisode(rssUrl, episodeIndex);
      setCurrentJobId(data.job_id);
      setCurrentJobInfo({
        podcastName: rssUrl,
        episodeTitle: episodes[episodeIndex].title,
        rssUrl: rssUrl
      });
      closeSearchModal();
    } catch (err) {
      handleError(err as Error);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSearchPodcasts = async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await searchPodcasts(searchQuery);
      setSearchResults(data);
    } catch (err) {
      handleError(err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteJob = async (jobId: string) => {
    try {
      await deleteJob(jobId);
      setCurrentJobs((prevJobs) => prevJobs.filter((job) => job.job_id !== jobId));
      if (jobId === currentJobId) {
        setCurrentJobId(null);
      }
    } catch (err) {
      handleError(err as Error);
    }
  };

  const handleFetchJobStatuses = useCallback(async () => {
    const jobIds = [...currentJobs.map(job => job.job_id), currentJobId].filter(Boolean) as string[];

    if (jobIds.length === 0) return;

    try {
      const data = await fetchJobStatuses(jobIds);
      setJobStatuses(prevStatuses => ({
        ...prevStatuses,
        ...data
      }));

      // Check for completed or failed jobs
      Object.entries(data).forEach(([jobId, status]) => {
        if (status.status === 'completed' || status.status === 'failed') {
          if (jobId === currentJobId) {
            setCurrentJobId(null);
            setIsProcessing(false);
          }
          setCurrentJobs(prevJobs => prevJobs.filter(job => job.job_id !== jobId));
        }
      });

      if (Object.values(data).some(status => status.status === 'completed' || status.status === 'failed')) {
        const { processed, autoProcessed } = await getProcessedPodcasts();
        setProcessedPodcasts(processed);
        setAutoPodcasts(autoProcessed);
      }
    } catch (error) {
      console.error('Error fetching job statuses:', error);
    }
  }, [currentJobs, currentJobId]);

  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;

    const startPolling = () => {
      handleFetchJobStatuses();
      intervalId = setInterval(handleFetchJobStatuses, 10000);
    };

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    if (currentJobs.length > 0 || currentJobId) {
      startPolling();
    } else {
      stopPolling();
    }

    return () => {
      stopPolling();
    };
  }, [currentJobs, currentJobId, handleFetchJobStatuses]);

  const handleDeletePodcast = async (podcastTitle: string, episodeTitle: string) => {
    try {
      await deleteProcessedPodcast(podcastTitle, episodeTitle);
      // After successful deletion, refresh the list of processed podcasts
      const { processed, autoProcessed } = await getProcessedPodcasts();
      setProcessedPodcasts(processed);
      setAutoPodcasts(autoProcessed);
    } catch (error) {
      console.error('Error deleting podcast:', error);
      setError(error instanceof Error ? error.message : 'Failed to delete podcast. Please try again.');
    }
  };

  const getFirebaseUrl = useCallback(async (path: string) => {
    return await getFileUrl(path);
  }, []);

  const openSearchModal = () => setIsSearchModalOpen(true);
  const closeSearchModal = () => {
    setIsSearchModalOpen(false);
    setSearchQuery('');
    setSearchResults([]);
  };

  const handleSelectPodcast = (podcast: SearchResult) => {
    setSelectedPodcast(podcast);
    setRssUrl(podcast.rssUrl);
    fetchPodcastEpisodes(podcast.rssUrl);
  };

  const handlePodcastSelect = useCallback(async (rssUrl: string) => {
    setRssUrl(rssUrl);
    closeSearchModal();
    await fetchPodcastEpisodes(rssUrl);
  }, [fetchPodcastEpisodes]);

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;
    setIsLoading(true);
    setError('');
    try {
      const results = await searchPodcasts(searchQuery);
      setSearchResults(results);
    } catch (err) {
      handleError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery]);

  const handleEnableAutoProcessing = async (podcast: SearchResult) => {
    try {
      await enableAutoProcessing(podcast.rssUrl);
      await savePodcastInfo(podcast);

      setAutoPodcasts(prev => [...prev, podcast.rssUrl]);
      setPodcastInfo(prev => ({
        ...prev,
        [podcast.rssUrl]: { name: podcast.name, imageUrl: podcast.imageUrl }
      }));

      setNotification('Auto-processing enabled for this podcast.');
      closeSearchModal();
    } catch (error) {
      console.error('Error enabling auto-processing:', error);
      setError(error instanceof Error ? error.message : 'Failed to enable auto-processing. Please try again.');
    }
  };

  // Add this function to clear the notification after a delay
  const clearNotification = useCallback(() => {
    setTimeout(() => {
      setNotification(null);
    }, 5000); // Clear after 5 seconds
  }, []);

  // Use useEffect to call clearNotification when notification changes
  useEffect(() => {
    if (notification) {
      clearNotification();
    }
  }, [notification, clearNotification]);

  const handleSelectAutoPodcast = useCallback(async (rssUrl: string) => {
    setIsLoadingEpisodes(true);
    try {
      await fetchPodcastEpisodes(rssUrl);
    } finally {
      setIsLoadingEpisodes(false);
    }
  }, [fetchPodcastEpisodes]);

  const handleEpisodeSelect = (rssUrl: string, episodeIndex: number) => {
    setSelectedEpisodeIndex(episodeIndex);
  };

  const handleProcessSelectedEpisode = async (rssUrl: string, episodeIndex: number) => {
    setIsProcessingEpisode(true);
    try {
      await handleProcessEpisode(rssUrl, episodeIndex);
    } finally {
      setIsProcessingEpisode(false);
    }
  };

  const togglePodcastExpansion = (rssUrl: string) => {
    setExpandedPodcasts(prev =>
      prev.includes(rssUrl)
        ? prev.filter(url => url !== rssUrl)
        : [...prev, rssUrl]
    );
  };

  const renderSearchResults = () => {
    return (
      <div className="search-results">
        {searchResults.map((result) => (
          <div key={result.uuid} className="search-result">
            <img src={result.imageUrl} alt={result.name} className="podcast-image" />
            <div className="podcast-info">
              <h3>{result.name}</h3>
              <p>{result.description}</p>
              {autoPodcasts.includes(result.rssUrl) ? (
                <span className="auto-processing-badge">Auto-processing enabled</span>
              ) : (
                <button onClick={() => handleEnableAutoProcessing(result)}>
                  Enable Auto-processing
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    );
  };

  const fetchCurrentJobsData = useCallback(async () => {
    try {
      const jobs = await fetchCurrentJobs();
      setCurrentJobs(jobs);
    } catch (error) {
      handleError(error as Error);
    }
  }, []);

  const handleLinkClick = (e: React.MouseEvent) => {
    e.preventDefault();
    // Add any necessary logic here
  };

  if (!isDataLoaded) {
    return <div>Loading...</div>;
  }

  return (
    <div className="App">
      <header className="App-header">
        <h1>Podcast Content Optimizer</h1>
        <button onClick={toggleTheme} className="theme-toggle">
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
      </header>
      <main className="App-main">
        {notification && (
          <div className="notification">
            {notification}
            <button onClick={() => setNotification(null)} className="close-notification">×</button>
          </div>
        )}
        <section className="search-section" aria-labelledby="search-heading">
          <h2 id="search-heading">Find and Process a Podcast</h2>
          <button onClick={openSearchModal} className="open-search-button">
            Search for Podcasts
          </button>
        </section>

        <section className="current-jobs" aria-labelledby="current-jobs-heading">
          <h2 id="current-jobs-heading">Current Processing Jobs</h2>
          {currentJobId && (
            <ProcessingStatus
              jobId={currentJobId}
              status={jobStatuses[currentJobId]}
              onDelete={() => handleDeleteJob(currentJobId)}
              podcastName={podcastInfo[currentJobInfo?.rssUrl || '']?.name || currentJobInfo?.podcastName}
              episodeTitle={currentJobInfo?.episodeTitle}
              podcastImageUrl={podcastInfo[currentJobInfo?.rssUrl || '']?.imageUrl}
            />
          )}
          {currentJobs.map((job) => (
            <ProcessingStatus
              key={job.job_id}
              jobId={job.job_id}
              status={jobStatuses[job.job_id]}
              onDelete={() => handleDeleteJob(job.job_id)}
              podcastName={podcastInfo[job.rss_url]?.name || job.podcast_name}
              episodeTitle={job.episode_title}
              podcastImageUrl={podcastInfo[job.rss_url]?.imageUrl}
            />
          ))}
          {!currentJobId && currentJobs.length === 0 && (
            <p className="no-jobs">No active processing jobs.</p>
          )}
        </section>

        <section className="processed-podcasts" aria-labelledby="processed-heading">
          <h2 id="processed-heading">Processed Podcasts</h2>
          {(Object.keys(processedPodcasts).length > 0 || autoPodcasts.length > 0) ? (
            <div>
              <h3>Manually Processed Episodes</h3>
              <ul className="processed-list">
                {Object.entries(processedPodcasts).map(([rssUrl, episodes]) => (
                  episodes.map((podcast, index) => (
                    <li key={`${rssUrl}-${index}`} className="processed-item">
                      <h4>{podcast.podcast_title} - {podcast.episode_title}</h4>
                      <div className="processed-links">
                        {podcast.edited_url && (
                          <PreventDefaultLink
                            onClick={async () => {
                              const url = await getFileUrl(podcast.edited_url);
                              if (url) window.open(url, '_blank');
                            }}
                            className="view-link"
                          >
                            Download Edited Audio
                          </PreventDefaultLink>
                        )}
                        {podcast.transcript_file && (
                          <PreventDefaultLink
                            onClick={async () => {
                              const url = await getFileUrl(podcast.transcript_file);
                              if (url) window.open(url, '_blank');
                            }}
                            className="view-link"
                          >
                            View Transcript
                          </PreventDefaultLink>
                        )}
                        {podcast.unwanted_content_file && (
                          <PreventDefaultLink
                            onClick={async () => {
                              const url = await getFileUrl(podcast.unwanted_content_file);
                              if (url) window.open(url, '_blank');
                            }}
                            className="view-link"
                          >
                            View Unwanted Content
                          </PreventDefaultLink>
                        )}
                        {podcast.rss_url && (
                          <PreventDefaultLink
                            onClick={() => window.open(`${API_BASE_URL}/api/modified_rss/${encodeURIComponent(podcast.rss_url)}`, '_blank')}
                            className="view-link"
                          >
                            View Modified RSS Feed
                          </PreventDefaultLink>
                        )}
                      </div>
                      <button
                        onClick={() => handleDeletePodcast(podcast.podcast_title, podcast.episode_title)}
                        className="delete-podcast-button"
                      >
                        Delete Podcast
                      </button>
                    </li>
                  ))
                ))}
              </ul>

              <section className="auto-processed-podcasts" aria-labelledby="auto-processed-heading">
                <h2 id="auto-processed-heading">Auto-processed Podcasts</h2>
                {autoPodcasts.length > 0 ? (
                  <ul className="auto-processed-list">
                    {autoPodcasts.map((rssUrl, index) => (
                      <AutoProcessedPodcast
                        key={`auto-${index}`}
                        rssUrl={rssUrl}
                        // Remove the episodes prop
                        podcastInfo={podcastInfo[rssUrl]}
                        onProcessEpisode={handleProcessSelectedEpisode}
                        onSelectPodcast={handleSelectAutoPodcast}
                        isLoadingEpisodes={isLoadingEpisodes}
                        isProcessingEpisode={isProcessingEpisode}
                      />
                    ))}
                  </ul>
                ) : (
                  <p className="no-podcasts">No auto-processed podcasts available. Enable auto-processing for a podcast to see it here.</p>
                )}
              </section>
            </div>
          ) : (
            <p className="no-podcasts">No processed podcasts available. Process an episode to see results here.</p>
          )}
        </section>

        {error && (
          <div className="error-message" role="alert">
            {error}
            <button onClick={() => setError('')} className="close-error">×</button>
          </div>
        )}

        <section className="prompt-editor-section">
          <h2>Edit Processing Prompt</h2>
          <PromptEditor />
        </section>

        <Modal
          isOpen={isSearchModalOpen}
          onRequestClose={closeSearchModal}
          contentLabel="Search Podcasts"
          className="search-modal"
          overlayClassName="search-modal-overlay"
        >
          <h2>Search Podcasts</h2>
          <form onSubmit={(e) => { e.preventDefault(); handleSearch(); }}>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter podcast name"
            />
            <button type="submit">Search</button>
          </form>
          {renderSearchResults()}
          <button onClick={closeSearchModal} className="close-modal-button">Close</button>
        </Modal>
      </main>

      {isProcessingEpisode && currentJobId && (
        <section className="processing-status" aria-labelledby="processing-status-heading">
          <h2 id="processing-status-heading">Processing Status</h2>
          <ProcessingStatus
            jobId={currentJobId}
            status={jobStatuses[currentJobId]}
            onDelete={() => currentJobId && handleDeleteJob(currentJobId)}
            podcastName={currentJobInfo?.podcastName}
            episodeTitle={currentJobInfo?.episodeTitle}
          />
        </section>
      )}
    </div>
  );
};

export default App;
