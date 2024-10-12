import React, { useState } from 'react';
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
}

const AutoProcessedPodcast: React.FC<AutoProcessedPodcastProps> = ({
  rssUrl,
  episodes,
  onProcessEpisode,
  onSelectPodcast,
  isLoadingEpisodes,
  isProcessingEpisode,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedEpisodeIndex, setSelectedEpisodeIndex] = useState<number | null>(null);

  const handleToggleExpand = async () => {
    if (!isExpanded) {
      await onSelectPodcast(rssUrl);
    }
    setIsExpanded(!isExpanded);
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
      <h4>{rssUrl}</h4>
      <button onClick={handleToggleExpand} disabled={isLoadingEpisodes}>
        {isExpanded ? 'Hide Episodes' : 'Show Episodes'}
      </button>
      {isLoadingEpisodes && <p>Loading episodes...</p>}
      {isExpanded && !isLoadingEpisodes && (
        <div>
          <select
            onChange={(e) => handleEpisodeSelect(parseInt(e.target.value))}
            value={selectedEpisodeIndex !== null ? selectedEpisodeIndex : ''}
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
          <a href={`${API_BASE_URL}/api/modified_rss/${encodeURIComponent(rssUrl)}`} target="_blank" rel="noopener noreferrer" className="view-link">
            View Modified RSS Feed
          </a>
        </div>
      )}
    </li>
  );
};

export default AutoProcessedPodcast;
