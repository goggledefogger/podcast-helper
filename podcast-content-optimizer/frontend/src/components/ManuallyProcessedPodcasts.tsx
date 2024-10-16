import React from 'react';
import ProcessedEpisode from './ProcessedEpisode';
import './ManuallyProcessedPodcasts.css';

interface ManuallyProcessedPodcastsProps {
  processedPodcasts: Record<string, any[]>;
  onDeletePodcast: (podcastTitle: string, episodeTitle: string) => void;
}

const ManuallyProcessedPodcasts: React.FC<ManuallyProcessedPodcastsProps> = ({ processedPodcasts, onDeletePodcast }) => {
  return (
    <section className="manually-processed-podcasts" aria-labelledby="manually-processed-heading">
      <h3 id="manually-processed-heading">Manually Processed Episodes</h3>
      <ul className="processed-list">
        {Object.entries(processedPodcasts).map(([rssUrl, episodes]) => (
          episodes.map((podcast, index) => (
            <ProcessedEpisode
              key={`${rssUrl}-${index}`}
              podcast={podcast}
              onDelete={onDeletePodcast}
            />
          ))
        ))}
      </ul>
    </section>
  );
};

export default ManuallyProcessedPodcasts;
