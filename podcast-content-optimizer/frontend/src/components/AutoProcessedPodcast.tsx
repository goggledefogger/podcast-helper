import React, { useState } from 'react';
import { FaPodcast, FaChevronDown, FaChevronUp } from 'react-icons/fa';
import { API_BASE_URL } from '../api';

interface Episode {
  number: number;
  title: string;
  published: string;
  duration: number;
}

interface AutoProcessedPodcastProps {
  rssUrl: string;
  episodes: Episode[];
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
  onProcessEpisode,
  onSelectPodcast,
  isLoadingEpisodes,
  isProcessingEpisode,
  isExpanded,
  onToggleExpand,
}) => {
  const [selectedEpisodeIndex, setSelectedEpisodeIndex] = useState<number | null>(null);

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
        <FaPodcast className="podcast-icon" />
        <h4>{rssUrl}</h4>
        {isExpanded ? <FaChevronUp /> : <FaChevronDown />}
      </div>
      {isLoadingEpisodes && <p className="loading-message">Loading episodes...</p>}
      {isExpanded && !isLoadingEpisodes && (
        <div className="auto-processed-content">
          <select
            onChange={(e) => handleEpisodeSelect(parseInt(e.target.value))}
            value={selectedEpisodeIndex !== null ? selectedEpisodeIndex : ''}
            className="episode-select"
          >
            <option value="">Select an episode to process</option>
            {episodes.map((episode, idx) => (
              <option key={idx} value={idx}>{episode.title}</option>
            ))}
          </select>
          <button
            onClick={handleProcessSelectedEpisode}
            disabled={selectedEpisodeIndex === null || isProcessingEpisode}
            className="process-episode-button"
          >
            {isProcessingEpisode ? 'Processing...' : 'Process Episode'}
          </button>
          <a href={`${API_BASE_URL}/api/modified_rss/${encodeURIComponent(rssUrl)}`} target="_blank" rel="noopener noreferrer" className="view-rss-link">
            View Modified RSS Feed
          </a>
        </div>
      )}
    </li>
  );
};

export default AutoProcessedPodcast;
