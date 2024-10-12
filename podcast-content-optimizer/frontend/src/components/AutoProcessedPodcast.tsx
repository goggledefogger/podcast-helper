import React, { useState } from 'react';
import { FaPodcast, FaChevronDown, FaChevronUp } from 'react-icons/fa';
import { API_BASE_URL } from '../api';
import { formatDuration, formatDate } from '../utils/timeUtils';
import './AutoProcessedPodcast.css';

interface Episode {
  number: number;
  title: string;
  published: string;
  duration: number;
}

interface PodcastInfo {
  name: string;
  imageUrl: string;
}

interface AutoProcessedPodcastProps {
  rssUrl: string;
  episodes: Episode[];
  podcastInfo?: PodcastInfo;
  onProcessEpisode: (rssUrl: string, episodeIndex: number) => Promise<void>;
  onSelectPodcast: (rssUrl: string) => Promise<void>;
  isLoadingEpisodes: boolean;
  isProcessingEpisode: boolean;
  isExpanded: boolean;
  onToggleExpand: () => void;
}

const AutoProcessedPodcast: React.FC<AutoProcessedPodcastProps> = ({
  rssUrl,
  episodes,
  podcastInfo,
  onProcessEpisode,
  onSelectPodcast,
  isLoadingEpisodes,
  isProcessingEpisode,
  isExpanded,
  onToggleExpand,
}) => {
  const [selectedEpisodeIndex, setSelectedEpisodeIndex] = useState<number | null>(null);

  console.log('AutoProcessedPodcast props:', { rssUrl, podcastInfo }); // Add this line for debugging

  const handleToggleExpand = async () => {
    if (!isExpanded) {
      await onSelectPodcast(rssUrl);
    }
    onToggleExpand();
  };

  const handleEpisodeSelect = (episodeIndex: number) => {
    setSelectedEpisodeIndex(episodeIndex);
  };

  const handleProcessSelectedEpisode = async () => {
    if (selectedEpisodeIndex !== null) {
      await onProcessEpisode(rssUrl, selectedEpisodeIndex);
      setSelectedEpisodeIndex(null);
    }
  };

  return (
    <li className="auto-processed-item">
      <div className="auto-processed-header" onClick={handleToggleExpand}>
        {podcastInfo && podcastInfo.imageUrl && (
          <img src={podcastInfo.imageUrl} alt={podcastInfo.name} className="podcast-image" />
        )}
        <FaPodcast className="podcast-icon" />
        <div className="podcast-title-container">
          <h4>{podcastInfo ? podcastInfo.name : 'Loading...'}</h4>
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
              {episodes.map((episode, idx) => (
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
          <a href={`${API_BASE_URL}/api/modified_rss/${encodeURIComponent(rssUrl)}`} target="_blank" rel="noopener noreferrer" className="view-rss-link">
            View Modified RSS Feed
          </a>
        </div>
      )}
    </li>
  );
};

export default AutoProcessedPodcast;
