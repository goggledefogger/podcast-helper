import React, { useState, useEffect } from 'react';
import { FaChevronDown, FaChevronUp, FaCopy, FaTrash } from 'react-icons/fa';
import Loader from './Loader';
import { API_BASE_URL } from '../api';
import { formatDuration, formatDate } from '../utils/timeUtils';
import './AutoProcessedPodcast.css';
import { usePodcastContext } from '../contexts/PodcastContext';

interface AutoProcessedPodcastProps {
  rssUrl: string;
  enabledAt: string;
}

const AutoProcessedPodcast: React.FC<AutoProcessedPodcastProps> = ({ rssUrl, enabledAt }) => {
  const {
    podcastInfo,
    episodes,
    fetchEpisodes,
    isProcessingEpisode,
    handleProcessEpisode,
    handleSelectPodcast,
    processedPodcasts,
    deleteAutoProcessedPodcast
  } = usePodcastContext();
  const [isExpanded, setIsExpanded] = useState(false);
  const [isLoadingEpisodes, setIsLoadingEpisodes] = useState(false);
  const [selectedEpisodeIndex, setSelectedEpisodeIndex] = useState<number | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (isExpanded && !episodes[rssUrl]) {
      setIsLoadingEpisodes(true);
      fetchEpisodes(rssUrl).finally(() => setIsLoadingEpisodes(false));
    }
  }, [isExpanded, rssUrl, episodes, fetchEpisodes]);

  const handleToggleExpand = async () => {
    if (!isExpanded) {
      await handleSelectPodcast(rssUrl);
    }
    setIsExpanded(!isExpanded);
  };

  const handleEpisodeSelect = (episodeIndex: number) => {
    setSelectedEpisodeIndex(episodeIndex);
  };

  const handleProcessSelectedEpisode = async () => {
    if (selectedEpisodeIndex !== null) {
      await handleProcessEpisode(rssUrl, selectedEpisodeIndex);
      setSelectedEpisodeIndex(null);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      console.log('Link copied to clipboard');
    }, (err) => {
      console.error('Could not copy text: ', err);
    });
  };

  const isEpisodeProcessed = (episodeTitle: string) => {
    return processedPodcasts[rssUrl]?.some(podcast => podcast.episode_title === episodeTitle);
  };

  const formatEnabledAt = (dateString: string) => {
    const date = new Date(dateString);
    return isNaN(date.getTime()) ? 'Recently enabled' : date.toLocaleString();
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent expanding/collapsing when clicking delete
    if (window.confirm('Are you sure you want to delete this auto-processed podcast?')) {
      setIsDeleting(true);
      try {
        await deleteAutoProcessedPodcast(rssUrl);
      } catch (error) {
        console.error('Error deleting auto-processed podcast:', error);
      } finally {
        setIsDeleting(false);
      }
    }
  };

  return (
    <li className="auto-processed-item">
      <div className="auto-processed-header" onClick={handleToggleExpand}>
        <div className="auto-processed-header-content">
          {podcastInfo[rssUrl]?.imageUrl && (
            <img
              src={podcastInfo[rssUrl].imageUrl}
              alt={podcastInfo[rssUrl].name || 'Podcast'}
              className="podcast-image"
            />
          )}
          <div className="podcast-title-container">
            <h4>{podcastInfo[rssUrl]?.name || 'Loading...'}</h4>
            <p className="rss-url">{rssUrl}</p>
            <p className="enabled-at">Enabled at: {formatEnabledAt(enabledAt)}</p>
          </div>
          {isExpanded ? <FaChevronUp /> : <FaChevronDown />}
        </div>
      </div>
      {isExpanded && (
        <div className="auto-processed-content">
          <div className="auto-processed-actions">
            <button
              onClick={handleDelete}
              disabled={isDeleting}
              className="delete-auto-processed-button"
              title="Delete auto-processed podcast"
            >
              <FaTrash /> Delete
            </button>
          </div>
          {isLoadingEpisodes ? (
            <Loader />
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); handleProcessSelectedEpisode(); }}>
              <select
                onChange={(e) => handleEpisodeSelect(parseInt(e.target.value))}
                value={selectedEpisodeIndex !== null ? selectedEpisodeIndex : ''}
                className="episode-select"
              >
                <option value="">Select an episode to process</option>
                {episodes[rssUrl]?.map((episode, idx) => (
                  <option key={idx} value={idx}>
                    {episode.title}
                    {isEpisodeProcessed(episode.title) ? ' (Optimized)' : ''}
                    {' - '}
                    {formatDate(episode.published)} ({formatDuration(episode.duration)})
                  </option>
                ))}
              </select>
              <button
                type="submit"
                disabled={selectedEpisodeIndex === null || isProcessingEpisode}
                className="process-episode-button"
              >
                {isProcessingEpisode ? 'Processing...' : 'Process Episode'}
              </button>
            </form>
          )}
          <div className="rss-links">
            <div className="rss-link-container">
              <label>Original RSS Feed:</label>
              <div className="rss-url-wrapper">
                <input type="text" value={rssUrl} readOnly className="rss-url-input" />
                <button onClick={() => copyToClipboard(rssUrl)} className="copy-button">
                  <FaCopy />
                </button>
              </div>
            </div>
            <div className="rss-link-container">
              <label>Modified RSS Feed:</label>
              <div className="rss-url-wrapper">
                <input
                  type="text"
                  value={`${API_BASE_URL}/api/modified_rss/${encodeURIComponent(rssUrl)}`}
                  readOnly
                  className="rss-url-input"
                />
                <button onClick={() => copyToClipboard(`${API_BASE_URL}/api/modified_rss/${encodeURIComponent(rssUrl)}`)} className="copy-button">
                  <FaCopy />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </li>
  );
};

export default AutoProcessedPodcast;
