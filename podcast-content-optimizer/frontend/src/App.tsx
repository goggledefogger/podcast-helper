import React, { useState, useEffect, useCallback } from 'react';
import Modal from 'react-modal'; // Add this import
import './App.css';
import ProcessingStatus from './components/ProcessingStatus';
import PromptEditor from './components/PromptEditor';
import AutoProcessedPodcast from './components/AutoProcessedPodcast';
import SearchModal from './components/SearchModal';
import { PodcastProvider, usePodcastContext } from './contexts/PodcastContext';
import PreventDefaultLink from './components/PreventDefaultLink';
import Loader from './components/Loader';
import Header from './components/Header';
import SearchSection from './components/SearchSection';
import ManuallyProcessedPodcasts from './components/ManuallyProcessedPodcasts';

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
    return <Loader fullPage />;
  }

  return (
    <div className="App">
      <Header theme={theme} toggleTheme={toggleTheme} />
      <main className="App-main">
        {notification && (
          <div className="notification">
            {notification}
            <button onClick={() => setNotification(null)} className="close-notification">×</button>
          </div>
        )}
        <SearchSection openSearchModal={() => setIsSearchModalOpen(true)} />

        <section className="current-jobs section-container" aria-labelledby="current-jobs-heading">
          <h2 id="current-jobs-heading" className="section-heading">Current Processing Jobs</h2>
          {currentJobs.length > 0 ? (
            currentJobs.map((job) => (
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
            ))
          ) : (
            <div className="empty-state-card">
              <p>No active processing jobs.</p>
            </div>
          )}
        </section>

        <section className="processed-podcasts section-container" aria-labelledby="processed-heading">
          <h2 id="processed-heading" className="section-heading">Processed Podcasts</h2>
          {Object.keys(processedPodcasts).length > 0 ? (
            <ManuallyProcessedPodcasts
              processedPodcasts={processedPodcasts}
              onDeletePodcast={handleDeletePodcast}
            />
          ) : (
            <div className="empty-state-card">
              <p>No manually processed podcasts available. Process an episode to see results here.</p>
            </div>
          )}
        </section>

        <section className="auto-processed-podcasts section-container" aria-labelledby="auto-processed-heading">
          <h2 id="auto-processed-heading" className="section-heading">Auto-processed Podcasts</h2>
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
            <div className="empty-state-card">
              <p>No auto-processed podcasts available. Enable auto-processing for a podcast to see it here.</p>
            </div>
          )}
        </section>

        <PromptEditor />

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
