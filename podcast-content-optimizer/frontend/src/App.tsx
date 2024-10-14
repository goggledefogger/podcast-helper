import React, { useState, useEffect, useCallback } from 'react';
import Modal from 'react-modal';
import './App.css';
import ProcessingStatus from './components/ProcessingStatus';
import { searchPodcasts } from './api';
import { getFileUrl } from './firebase';
import PromptEditor from './components/PromptEditor';
import { API_BASE_URL } from './api';
import AutoProcessedPodcast from './components/AutoProcessedPodcast';
import PreventDefaultLink from './components/PreventDefaultLink';
import { PodcastProvider, usePodcastContext } from './contexts/PodcastContext';

Modal.setAppElement('#root');

interface SearchResult {
  uuid: string;
  name: string;
  description: string;
  imageUrl: string;
  rssUrl: string;
}

const AppContent: React.FC = () => {
  const {
    podcastInfo,
    processedPodcasts,
    autoPodcasts,
    currentJobs,
    jobStatuses,
    jobInfos,
    isProcessingEpisode,
    error,
    setError,
    handleDeleteJob,
    handleDeletePodcast,
    handleEnableAutoProcessing,
    fetchJobStatuses,
    isLoading,
    fetchAllData
  } = usePodcastContext();

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [notification, setNotification] = useState<string | null>(null);
  const [isSearchLoading, setIsSearchLoading] = useState(false);

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null;
    if (savedTheme) {
      setTheme(savedTheme);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      setTheme('dark');
    }
  }, []);

  useEffect(() => {
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
    let intervalId: NodeJS.Timeout | null = null;

    const startPolling = () => {
      fetchJobStatuses();
      intervalId = setInterval(fetchJobStatuses, 10000);
    };

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    if (currentJobs.length > 0) {
      startPolling();
    } else {
      stopPolling();
    }

    return () => {
      stopPolling();
    };
  }, [currentJobs.length, fetchJobStatuses]); // Only depend on the length of currentJobs

  const openSearchModal = () => setIsSearchModalOpen(true);
  const closeSearchModal = () => {
    setIsSearchModalOpen(false);
    setSearchQuery('');
    setSearchResults([]);
  };

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;
    setIsSearchLoading(true);
    setError('');
    try {
      const results = await searchPodcasts(searchQuery);
      setSearchResults(results);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsSearchLoading(false);
    }
  }, [searchQuery, setError]);

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

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  if (isLoading) {
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
          {currentJobs.map((job) => (
            <ProcessingStatus
              key={job.job_id}
              jobId={job.job_id}
              status={jobStatuses[job.job_id]}
              onDelete={() => handleDeleteJob(job.job_id)}
              jobInfo={jobInfos[job.job_id]}
              podcastImageUrl={podcastInfo[job.rss_url]?.imageUrl}
            />
          ))}
          {currentJobs.length === 0 && (
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
            <button type="submit" disabled={isSearchLoading}>
              {isSearchLoading ? 'Searching...' : 'Search'}
            </button>
          </form>
          {renderSearchResults()}
          <button onClick={closeSearchModal} className="close-modal-button">Close</button>
        </Modal>
      </main>

      {isProcessingEpisode && (
        <section className="processing-status" aria-labelledby="processing-status-heading">
          <h2 id="processing-status-heading">Processing Status</h2>
          <ProcessingStatus
            jobId={currentJobs[0]?.job_id}
            status={jobStatuses[currentJobs[0]?.job_id]}
            onDelete={() => currentJobs[0]?.job_id && handleDeleteJob(currentJobs[0]?.job_id)}
            jobInfo={jobInfos[currentJobs[0]?.job_id]}
            podcastImageUrl={podcastInfo[jobInfos[currentJobs[0]?.job_id]?.rssUrl]?.imageUrl}
          />
        </section>
      )}
    </div>
  );
};

const App: React.FC = () => {
  return (
    <PodcastProvider>
      <AppContent />
    </PodcastProvider>
  );
};

export default App;
