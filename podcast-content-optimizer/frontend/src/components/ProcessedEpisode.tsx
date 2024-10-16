import React from 'react';
import PreventDefaultLink from './PreventDefaultLink';
import './ProcessedEpisode.css';

interface ProcessedEpisodeProps {
  podcast: {
    podcast_title: string;
    episode_title: string;
    edited_url: string;
    transcript_file: string;
    unwanted_content_file: string;
  };
  onDelete: (podcastTitle: string, episodeTitle: string) => void;
}

const ProcessedEpisode: React.FC<ProcessedEpisodeProps> = ({ podcast, onDelete }) => {
  return (
    <li className="processed-item">
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
        onClick={() => onDelete(podcast.podcast_title, podcast.episode_title)}
        className="delete-podcast-button"
      >
        Delete Episode
      </button>
    </li>
  );
};

export default ProcessedEpisode;