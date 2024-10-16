import React from 'react';
import ProcessedEpisode from './ProcessedEpisode';
import './ManuallyProcessedPodcasts.css';
import { usePodcastContext } from '../contexts/PodcastContext';

interface ManuallyProcessedPodcastsProps {
  processedPodcasts: Record<string, any[]>;
  onDeletePodcast: (podcastTitle: string, episodeTitle: string) => void;
}

const ManuallyProcessedPodcasts: React.FC<ManuallyProcessedPodcastsProps> = ({ processedPodcasts, onDeletePodcast }) => {
  const { currentJobs } = usePodcastContext();

  // Function to check if an episode is currently being processed
  const isEpisodeInProgress = (podcastTitle: string, episodeTitle: string) => {
    return currentJobs.some(job =>
      job.podcast_name === podcastTitle && job.episode_title === episodeTitle
    );
  };

  return (
    <section className="manually-processed-podcasts" aria-labelledby="manually-processed-heading">
      <h3 id="manually-processed-heading">Manually Processed Episodes</h3>
      <ul className="processed-list">
        {Object.entries(processedPodcasts).map(([rssUrl, episodes]) => (
          episodes.filter(podcast => !isEpisodeInProgress(podcast.podcast_title, podcast.episode_title))
            .map((podcast, index) => (
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
