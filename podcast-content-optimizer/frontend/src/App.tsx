import React, { useState, useEffect, useCallback } from 'react';
import Modal from 'react-modal';
import './App.css';
import ProcessingStatus from './components/ProcessingStatus';
import { formatDuration, formatDate } from './utils/timeUtils';
import {
  fetchEpisodes,
  processEpisode,
  searchPodcasts,
  fetchCurrentJobs,
  deleteJob,
  fetchJobStatuses,
  deleteProcessedPodcast,
  JobStatus
} from './api';
import { ProcessedPodcast, getProcessedPodcasts, getFileUrl } from './firebase';
import PromptEditor from './components/PromptEditor';
import { API_BASE_URL } from './api';

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
  const [selectedEpisode, setSelectedEpisode] = useState<number | null>(null);
  const [processedPodcasts, setProcessedPodcasts] = useState<ProcessedPodcast[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [currentJobs, setCurrentJobs] = useState<{ job_id: string; status: JobStatus }[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [jobStatuses, setJobStatuses] = useState<Record<string, JobStatus>>({});
  const [currentJobInfo, setCurrentJobInfo] = useState<{ podcastName: string; episodeTitle: string } | null>(null);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [selectedPodcast, setSelectedPodcast] = useState<SearchResult | null>(null);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

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
        const podcasts = await getProcessedPodcasts();
        setProcessedPodcasts(podcasts);
      } catch (error) {
        handleError(error as Error);
      }
    };

    fetchData();
    fetchCurrentJobs().then(setCurrentJobs).catch(handleError);
  }, []);

  const handleError = (error: Error) => {
    console.error('Error:', error);
    setError(error.message);
  };

  const fetchPodcastEpisodes = async (url: string) => {
    setIsLoading(true);
    setError('');
    try {
      const data = await fetchEpisodes(url);
      setEpisodes(data);
    } catch (err) {
      handleError(err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleProcessEpisode = async () => {
    if (selectedEpisode === null || !selectedPodcast) return;
    setError('');
    setIsProcessing(true);

    try {
      const data = await processEpisode(rssUrl, selectedEpisode);
      setCurrentJobId(data.job_id);
      setCurrentJobInfo({
        podcastName: selectedPodcast.name,
        episodeTitle: episodes[selectedEpisode].title
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
        const updatedPodcasts = await getProcessedPodcasts();
        setProcessedPodcasts(updatedPodcasts);
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
      const updatedPodcasts = await getProcessedPodcasts();
      setProcessedPodcasts(updatedPodcasts);
    } catch (error) {
      console.error('Error deleting podcast:', error);
      setError('Failed to delete podcast. Please try again.');
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
    setSelectedPodcast(null);
    setEpisodes([]);
    setSelectedEpisode(null);
  };

  const handleSelectPodcast = (podcast: SearchResult) => {
    setSelectedPodcast(podcast);
    setRssUrl(podcast.rssUrl);
    fetchPodcastEpisodes(podcast.rssUrl);
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Podcast Content Optimizer</h1>
        <button onClick={toggleTheme} className="theme-toggle">
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
      </header>
      <main className="App-main">
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
              podcastName={currentJobInfo?.podcastName}
              episodeTitle={currentJobInfo?.episodeTitle}
            />
          )}
          {currentJobs.map((job) => (
            <div key={job.job_id} className="job-item">
              <ProcessingStatus
                jobId={job.job_id}
                status={jobStatuses[job.job_id]}
                onDelete={() => handleDeleteJob(job.job_id)}
              />
            </div>
          ))}
          {!currentJobId && currentJobs.length === 0 && (
            <p className="no-jobs">No active processing jobs.</p>
          )}
        </section>

        <section className="processed-podcasts" aria-labelledby="processed-heading">
          <h2 id="processed-heading">Processed Podcasts</h2>
          {processedPodcasts.length > 0 ? (
            <ul className="processed-list">
              {processedPodcasts.map((podcast, index) => (
                podcast && podcast.podcast_title && podcast.episode_title ? (
                  <li key={index} className="processed-item">
                    <h3>{podcast.podcast_title} - {podcast.episode_title}</h3>
                    <div className="processed-links">
                      {podcast.edited_url && (
                        <a
                          href="#"
                          onClick={async (e) => {
                            e.preventDefault();
                            const url = await getFirebaseUrl(podcast.edited_url);
                            if (url) window.open(url, '_blank');
                          }}
                          className="view-link"
                        >
                          Download Edited Audio
                        </a>
                      )}
                      {podcast.transcript_file && (
                        <a
                          href="#"
                          onClick={async (e) => {
                            e.preventDefault();
                            const url = await getFirebaseUrl(podcast.transcript_file);
                            if (url) window.open(url, '_blank');
                          }}
                          className="view-link"
                        >
                          View Transcript
                        </a>
                      )}
                      {podcast.unwanted_content_file && (
                        <a
                          href="#"
                          onClick={async (e) => {
                            e.preventDefault();
                            const url = await getFirebaseUrl(podcast.unwanted_content_file);
                            if (url) window.open(url, '_blank');
                          }}
                          className="view-link"
                        >
                          View Unwanted Content
                        </a>
                      )}
                      {podcast.rss_url && (
                        <a href={`${API_BASE_URL}/api/modified_rss/${encodeURIComponent(podcast.rss_url)}`} target="_blank" rel="noopener noreferrer" className="view-link">
                          View Modified RSS Feed
                        </a>
                      )}
                    </div>
                    <button
                      onClick={() => handleDeletePodcast(podcast.podcast_title, podcast.episode_title)}
                      className="delete-podcast-button"
                    >
                      Delete Podcast
                    </button>
                  </li>
                ) : null
              ))}
            </ul>
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
          contentLabel="Search and Process Podcasts"
          className="search-modal"
          overlayClassName="search-modal-overlay"
        >
          <h2>Search and Process Podcasts</h2>
          {!selectedPodcast ? (
            <>
              <form onSubmit={(e) => { e.preventDefault(); handleSearchPodcasts(); }} className="search-container">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Enter podcast name"
                  aria-label="Search for podcasts"
                />
                <button type="submit" disabled={isLoading || !searchQuery.trim()}>
                  Search
                </button>
              </form>
              {isLoading && <p>Searching...</p>}
              {searchResults.length > 0 && (
                <ul className="podcast-list">
                  {searchResults.map((podcast) => (
                    <li key={podcast.uuid} className="podcast-item">
                      <div className="podcast-info">
                        <h4>{podcast.name}</h4>
                        <p>{podcast.description}</p>
                      </div>
                      {podcast.imageUrl && (
                        <img src={podcast.imageUrl} alt={`${podcast.name} cover`} className="podcast-image" />
                      )}
                      <button onClick={() => handleSelectPodcast(podcast)} className="select-button">
                        Select
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <>
              <h3>{selectedPodcast.name}</h3>
              <form onSubmit={(e) => { e.preventDefault(); handleProcessEpisode(); }} className="episode-container">
                <select
                  id="episode-select"
                  value={selectedEpisode ?? ''}
                  onChange={(e) => setSelectedEpisode(Number(e.target.value))}
                  className="episode-select"
                  disabled={isProcessing}
                >
                  <option value="">Select an episode</option>
                  {episodes.map((episode, index) => (
                    <option key={index} value={index}>
                      {episode.title} - {formatDate(episode.published)} ({formatDuration(episode.duration, 'MM:SS')})
                    </option>
                  ))}
                </select>
                <button
                  type="submit"
                  disabled={isLoading || selectedEpisode === null || isProcessing}
                  className="process-button"
                >
                  {isProcessing ? 'Processing...' : 'Process Episode'}
                </button>
              </form>
            </>
          )}
          <button onClick={closeSearchModal} className="close-modal-button">Close</button>
        </Modal>
      </main>
    </div>
  );
};

export default App;
