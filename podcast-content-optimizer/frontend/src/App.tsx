import React, { useState, useEffect, useCallback } from 'react';
import Modal from 'react-modal';
import './App.css';
import ProcessingStatus from './components/ProcessingStatus';
import PromptEditor from './components/PromptEditor';
import AutoProcessedPodcast from './components/AutoProcessedPodcast';
import SearchModal from './components/SearchModal';
import { PodcastProvider, usePodcastContext } from './contexts/PodcastContext';
import Loader from './components/Loader';
import Header from './components/Header';
import SearchSection from './components/SearchSection';
import ManuallyProcessedPodcasts from './components/ManuallyProcessedPodcasts';

Modal.setAppElement('#root');

const AppContent: React.FC = () => {
  const {
    processedPodcasts,
    autoPodcasts,
    currentJobs,
    jobStatuses,
    jobInfos,
    isProcessingEpisode,
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
    if (currentJobs.length > 0) {
      fetchJobStatuses();
    }
  }, [currentJobs, fetchJobStatuses]);

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

  const activeJobs = currentJobs.filter(job => {
    const status = jobStatuses[job.job_id];
    return status && status.current_stage !== 'CLEANUP';
  });

  console.log('Active jobs:', activeJobs);
  console.log('Job infos:', jobInfos);

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
          {activeJobs.length > 0 ? (
            activeJobs.map((job) => (
              <ProcessingStatus
                key={job.job_id}
                jobId={job.job_id}
                status={jobStatuses[job.job_id]}
                onDelete={() => handleDeleteJob(job.job_id)}
                jobInfo={jobInfos[job.job_id]}
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

      {isProcessingEpisode && activeJobs.length > 0 && (
        <section className="processing-status" aria-labelledby="processing-status-heading">
          <h2 id="processing-status-heading">Processing Status</h2>
          <ProcessingStatus
            jobId={activeJobs[0].job_id}
            status={jobStatuses[activeJobs[0].job_id]}
            onDelete={() => handleDeleteJob(activeJobs[0].job_id)}
            jobInfo={jobInfos[activeJobs[0].job_id]}
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
