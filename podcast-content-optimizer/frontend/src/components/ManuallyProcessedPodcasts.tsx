import React from 'react';
import ProcessedEpisode from './ProcessedEpisode';
import './ManuallyProcessedPodcasts.css';
import { usePodcastContext } from '../contexts/PodcastContext';

interface ManuallyProcessedPodcastsProps {
  processedPodcasts: Record<string, any[]>;
  onDeletePodcast: (podcastTitle: string, episodeTitle: string) => Promise<void>;
}

const ManuallyProcessedPodcasts: React.FC<ManuallyProcessedPodcastsProps> = ({ processedPodcasts, onDeletePodcast }) => {
  const { currentJobs } = usePodcastContext();

  // Function to check if an episode is currently being processed
  const isEpisodeInProgress = (podcastTitle: string, episodeTitle: string) => {
    return currentJobs.some(job =>
      job.podcast_name === podcastTitle && job.episode_title === episodeTitle
    );
  };

  // Flatten and sort all processed episodes
  const sortedEpisodes = Object.entries(processedPodcasts)
    .flatMap(([rssUrl, episodes]) =>
      episodes
        .filter(episode => episode.status === 'completed')
        .map(episode => ({ ...episode, rssUrl }))
    )
    .sort((a, b) => {
      return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
    })
    .filter(episode => !isEpisodeInProgress(episode.podcast_title, episode.episode_title));

  return (
    <section className="manually-processed-podcasts" aria-labelledby="manually-processed-heading">
      <h3 id="manually-processed-heading">Manually Processed Episodes</h3>
      <ul className="processed-list">
        {sortedEpisodes.map((episode, index) => (
          <ProcessedEpisode
            key={`${episode.rssUrl}-${index}`}
            podcast={episode}
            onDelete={onDeletePodcast}
          />
        ))}
      </ul>
    </section>
  );
};

export default ManuallyProcessedPodcasts;
