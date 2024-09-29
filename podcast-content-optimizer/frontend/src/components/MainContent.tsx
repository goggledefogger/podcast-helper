import React, { useState, useEffect, useCallback } from 'react';
import { signInAnonymously } from 'firebase/auth';
import Modal from 'react-modal';
import { useQuery } from 'react-query';
import '../App.css';
import ProcessingStatus from './ProcessingStatus';
import { formatDuration, formatDate } from '../utils/timeUtils';
import {
  fetchEpisodes,
  processEpisode,
  searchPodcasts,
  deleteJob,
  fetchJobStatuses,
  deleteProcessedPodcast,
  JobStatus
} from '../api';
import { auth, getFileUrl } from '../firebase';
import PromptEditor from './PromptEditor';
import { useAppContext } from '../contexts/AppContext';

const MainContent: React.FC = () => {
  const { processedPodcasts, currentJobs, refreshData, isLoading } = useAppContext();
  const [rssUrl, setRssUrl] = useState('');
  const [episodes, setEpisodes] = useState<any[]>([]);
  const [selectedEpisode, setSelectedEpisode] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [selectedPodcast, setSelectedPodcast] = useState<any | null>(null);

  useEffect(() => {
    const signInAnonymouslyToFirebase = async () => {
      try {
        await signInAnonymously(auth);
        console.log("Signed in anonymously");
      } catch (error) {
        console.error("Error signing in anonymously:", error);
      }
    };

    signInAnonymouslyToFirebase();
  }, []);

  const { data: jobStatuses } = useQuery(
    ['jobStatuses', currentJobs],
    () => fetchJobStatuses(currentJobs.map(job => job.job_id)),
    {
      enabled: currentJobs.length > 0,
      refetchInterval: (data) => {
        if (data && Object.values(data).some(status => status.status === 'in_progress')) {
          return 5000; // Poll every 5 seconds if any job is in progress
        }
        return false; // Stop polling if all jobs are completed or failed
      },
    }
  );

  const handleFetchEpisodes = async () => {
    try {
      const fetchedEpisodes = await fetchEpisodes(rssUrl);
      setEpisodes(fetchedEpisodes);
    } catch (error) {
      console.error('Error fetching episodes:', error);
      setError('Failed to fetch episodes. Please try again.');
    }
  };

  const handleProcessEpisode = async () => {
    if (selectedEpisode !== null) {
      setIsProcessing(true);
      try {
        const data = await processEpisode(rssUrl, selectedEpisode);
        setCurrentJobId(data.job_id);
        refreshData();
      } catch (error) {
        console.error('Error processing episode:', error);
        setError('Failed to process episode. Please try again.');
      } finally {
        setIsProcessing(false);
      }
    }
  };

  const handleSearchPodcasts = async () => {
    try {
      const results = await searchPodcasts(searchQuery);
      setSearchResults(results);
    } catch (error) {
      console.error('Error searching podcasts:', error);
      setError('Failed to search podcasts. Please try again.');
    }
  };

  const handleDeleteJob = async (jobId: string) => {
    try {
      await deleteJob(jobId);
      refreshData();
    } catch (error) {
      console.error('Error deleting job:', error);
      setError('Failed to delete job. Please try again.');
    }
  };

  const handleDeletePodcast = async (podcastTitle: string, episodeTitle: string) => {
    try {
      await deleteProcessedPodcast(podcastTitle, episodeTitle);
      refreshData();
    } catch (error) {
      console.error('Error deleting podcast:', error);
      setError('Failed to delete podcast. Please try again.');
    }
  };

  const openSearchModal = () => setIsSearchModalOpen(true);
  const closeSearchModal = () => {
    setIsSearchModalOpen(false);
    setSearchQuery('');
    setSearchResults([]);
    setSelectedPodcast(null);
    setEpisodes([]);
    setSelectedEpisode(null);
  };

  const handleSelectPodcast = (podcast: any) => {
    setSelectedPodcast(podcast);
    setRssUrl(podcast.rssUrl);
    handleFetchEpisodes();
  };

  return (
    <div className="main-content">
      <h1>Podcast Content Optimizer</h1>
      {error && <div className="error-message">{error}</div>}
      <section className="search-section">
        <h2>Find and Process a Podcast</h2>
        <button onClick={openSearchModal} className="open-search-button">
          Search for Podcasts
        </button>
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
            <div className="search-container">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Enter podcast name"
              />
              <button onClick={handleSearchPodcasts}>Search</button>
            </div>
            {searchResults.length > 0 && (
              <ul className="podcast-list">
                {searchResults.map((podcast) => (
                  <li key={podcast.uuid} className="podcast-item">
                    <div className="podcast-info">
                      <h3>{podcast.name}</h3>
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
            <div className="episode-container">
              <select
                value={selectedEpisode ?? ''}
                onChange={(e) => setSelectedEpisode(Number(e.target.value))}
                disabled={isProcessing}
              >
                <option value="">Select an episode</option>
                {episodes.map((episode, index) => (
                  <option key={index} value={index}>
                    {episode.title} - {formatDate(episode.published)} ({formatDuration(episode.duration)})
                  </option>
                ))}
              </select>
              <button
                onClick={handleProcessEpisode}
                disabled={isProcessing || selectedEpisode === null}
                className="process-button"
              >
                {isProcessing ? 'Processing...' : 'Process Episode'}
              </button>
            </div>
          </>
        )}
        <button onClick={closeSearchModal} className="close-modal-button">Close</button>
      </Modal>

      <section className="current-jobs">
        <h2>Current Processing Jobs</h2>
        {currentJobs.map((job) => (
          <ProcessingStatus
            key={job.job_id}
            jobId={job.job_id}
            status={jobStatuses?.[job.job_id]}
            onDelete={() => handleDeleteJob(job.job_id)}
          />
        ))}
      </section>

      <section className="processed-podcasts">
        <h2>Processed Podcasts</h2>
        {processedPodcasts.length > 0 ? (
          <ul className="processed-list">
            {processedPodcasts.map((podcast, index) => (
              <li key={index} className="processed-item">
                <h3>{podcast.podcast_title} - {podcast.episode_title}</h3>
                <div className="processed-links">
                  {podcast.edited_url && (
                    <a href={podcast.edited_url} target="_blank" rel="noopener noreferrer" className="view-link">
                      Download Edited Audio
                    </a>
                  )}
                  {podcast.transcript_file && (
                    <a href={podcast.transcript_file} target="_blank" rel="noopener noreferrer" className="view-link">
                      View Transcript
                    </a>
                  )}
                  {podcast.unwanted_content_file && (
                    <a href={podcast.unwanted_content_file} target="_blank" rel="noopener noreferrer" className="view-link">
                      View Unwanted Content
                    </a>
                  )}
                  {podcast.rss_url && (
                    <a href={`${process.env.REACT_APP_API_BASE_URL}/api/modified_rss/${encodeURIComponent(podcast.rss_url)}`} target="_blank" rel="noopener noreferrer" className="view-link">
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
            ))}
          </ul>
        ) : (
          <p>No processed podcasts available. Process an episode to see results here.</p>
        )}
      </section>

      <PromptEditor />
    </div>
  );
};

export default MainContent;