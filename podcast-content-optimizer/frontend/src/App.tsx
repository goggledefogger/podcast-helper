import React, { useState, useEffect, useCallback } from 'react';
import Modal from 'react-modal'; // Add this import
import './App.css';
import ProcessingStatus from './components/ProcessingStatus';
import PromptEditor from './components/PromptEditor';
import AutoProcessedPodcast from './components/AutoProcessedPodcast';
import SearchModal from './components/SearchModal';
import { PodcastProvider, usePodcastContext } from './contexts/PodcastContext';
import PreventDefaultLink from './components/PreventDefaultLink';

// Add this line to set the app element
Modal.setAppElement('#root');

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
    fetchJobStatuses,
    isLoading,
    fetchAllData
  } = usePodcastContext();

  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [notification, setNotification] = useState<string | null>(null);

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
    setTheme(prevTheme => prevTheme === 'light' ? 'dark' : 'light');
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
  }, [currentJobs.length, fetchJobStatuses]);

  const openSearchModal = () => setIsSearchModalOpen(true);
  const closeSearchModal = () => setIsSearchModalOpen(false);

  const clearNotification = useCallback(() => {
    setTimeout(() => {
      setNotification(null);
    }, 5000);
  }, []);

  useEffect(() => {
    if (notification) {
      clearNotification();
    }
  }, [notification, clearNotification]);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  const handleNotification = (message: string) => {
    setNotification(message);
  };

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
              jobInfo={{
                podcastName: job.podcast_name || podcastInfo[job.rss_url]?.name || 'Unknown Podcast',
                episodeTitle: job.episode_title || 'Unknown Episode',
                rssUrl: job.rss_url
              }}
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
                        <PreventDefaultLink
                          onClick={() => window.open(podcast.edited_url, '_blank')}
                          className="view-link"
                        >
                          View Edited Audio
                        </PreventDefaultLink>
                        <PreventDefaultLink
                          onClick={() => window.open(podcast.transcript_file, '_blank')}
                          className="view-link"
                        >
                          View Transcript
                        </PreventDefaultLink>
                        <PreventDefaultLink
                          onClick={() => window.open(podcast.unwanted_content_file, '_blank')}
                          className="view-link"
                        >
                          View Unwanted Content
                        </PreventDefaultLink>
                      </div>
                      <button
                        onClick={() => handleDeletePodcast(podcast.podcast_title, podcast.episode_title)}
                        className="delete-podcast-button"
                      >
                        Delete Episode
                      </button>
                    </li>
                  ))
                ))}
              </ul>

              <section className="auto-processed-podcasts" aria-labelledby="auto-processed-heading">
                <h2 id="auto-processed-heading">Auto-processed Podcasts</h2>
                {autoPodcasts.length > 0 ? (
                  <ul className="auto-processed-list">
                    {autoPodcasts.map((podcast, index) => (
                      <AutoProcessedPodcast
                        key={`auto-${index}`}
                        rssUrl={podcast.rss_url}
                        enabledAt={podcast.enabled_at}
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

        <section className="prompt-editor-section">
          <h2>Edit Processing Prompt</h2>
          <PromptEditor />
        </section>

        <SearchModal
          isOpen={isSearchModalOpen}
          onRequestClose={closeSearchModal}
          onNotification={handleNotification}
        />
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
