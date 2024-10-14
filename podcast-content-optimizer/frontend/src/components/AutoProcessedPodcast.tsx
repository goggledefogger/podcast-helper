import React, { useState, useEffect } from 'react';
import { FaPodcast, FaChevronDown, FaChevronUp, FaCopy } from 'react-icons/fa';
import { API_BASE_URL } from '../api';
import { formatDuration, formatDate } from '../utils/timeUtils';
import './AutoProcessedPodcast.css';
import { usePodcastContext } from '../contexts/PodcastContext';

interface AutoProcessedPodcastProps {
  rssUrl: string;
}

const AutoProcessedPodcast: React.FC<AutoProcessedPodcastProps> = ({ rssUrl }) => {
  const {
    podcastInfo,
    episodes,
    fetchEpisodes,
    isLoadingEpisodes,
    isProcessingEpisode,
    handleProcessEpisode,
    handleSelectPodcast
  } = usePodcastContext();
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedEpisodeIndex, setSelectedEpisodeIndex] = useState<number | null>(null);

  useEffect(() => {
    if (isExpanded && !episodes[rssUrl]) {
      fetchEpisodes(rssUrl);
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

  return (
    <li className="auto-processed-item">
      <div className="auto-processed-header" onClick={handleToggleExpand}>
        {podcastInfo[rssUrl]?.imageUrl && (
          <img src={podcastInfo[rssUrl].imageUrl} alt={podcastInfo[rssUrl].name} className="podcast-image" />
        )}
        <FaPodcast className="podcast-icon" />
        <div className="podcast-title-container">
          <h4>{podcastInfo[rssUrl]?.name || 'Loading...'}</h4>
          <p className="rss-url">{rssUrl}</p>
        </div>
        {isExpanded ? <FaChevronUp /> : <FaChevronDown />}
      </div>
      {isLoadingEpisodes && <p className="loading-message">Loading episodes...</p>}
      {isExpanded && !isLoadingEpisodes && (
        <div className="auto-processed-content">
          <form onSubmit={(e) => { e.preventDefault(); handleProcessSelectedEpisode(); }}>
            <select
              onChange={(e) => handleEpisodeSelect(parseInt(e.target.value))}
              value={selectedEpisodeIndex !== null ? selectedEpisodeIndex : ''}
              className="episode-select"
            >
              <option value="">Select an episode to process</option>
              {episodes[rssUrl]?.map((episode, idx) => (
                <option key={idx} value={idx}>
                  {episode.title} - {formatDate(episode.published)} ({formatDuration(episode.duration)})
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
