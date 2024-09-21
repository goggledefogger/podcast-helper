import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import ProcessingStatus from './components/ProcessingStatus';
import { formatDuration } from './utils/timeUtils';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5001/api';

interface Episode {
  number: number;
  title: string;
  published: string;
  duration: number;  // Duration in seconds
}

interface ProcessedPodcast {
  podcast_title: string;
  episode_title: string;
  rss_url: string;
  edited_url: string;
  transcript_file: string;
  unwanted_content_file: string;
}

interface SearchResult {
  uuid: string;
  name: string;
  description: string;
  imageUrl: string;
  rssUrl: string;
}

interface JobStatus {
  status: 'queued' | 'in_progress' | 'completed' | 'failed';
  current_stage: string;
  progress: number;
  message: string;
  timestamp: number;
}

const fetchWithCredentials = (url: string, options: RequestInit = {}) => {
  console.log('Fetching URL:', url);
  return fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      ...options.headers,
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
  });
};

const App: React.FC = () => {
  const [rssUrl, setRssUrl] = useState('');
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [selectedEpisode, setSelectedEpisode] = useState<number | null>(null);
  const [processedPodcasts, setProcessedPodcasts] = useState<ProcessedPodcast[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [currentJobs, setCurrentJobs] = useState<{ job_id: string; status: JobStatus }[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [jobStatuses, setJobStatuses] = useState<{ [key: string]: JobStatus }>({});
  const [currentJobInfo, setCurrentJobInfo] = useState<{ podcastName: string; episodeTitle: string } | null>(null);

  useEffect(() => {
    fetchProcessedPodcasts();
    fetchCurrentJobs();
  }, []);

  const fetchProcessedPodcasts = async () => {
    try {
      const response = await fetchWithCredentials(`${API_BASE_URL}/processed_podcasts`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setProcessedPodcasts(data);
    } catch (err) {
      console.error('Error fetching processed podcasts:', err);
      setError('Error fetching processed podcasts. Please try again later.');
    }
  };

  const fetchJobStatuses = useCallback(async () => {
    const jobIds = [...currentJobs.map(job => job.job_id), currentJobId].filter(Boolean) as string[];

    if (jobIds.length === 0) return;

    try {
      const response = await fetchWithCredentials(`${API_BASE_URL}/batch_process_status`, {
        method: 'POST',
        body: JSON.stringify({ job_ids: jobIds }),
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const data: { [key: string]: JobStatus } = await response.json();

      setJobStatuses(prevStatuses => ({
        ...prevStatuses,
        ...data
      }));

      // Check for completed or failed jobs
      Object.entries(data).forEach(([jobId, status]) => {
        if (status.status === 'completed' || status.status === 'failed') {
          if (jobId === currentJobId) {
            setCurrentJobId(null);
            setIsProcessing(false);
          }
          setCurrentJobs(prevJobs => prevJobs.filter(job => job.job_id !== jobId));
        }
      });

      if (Object.values(data).some(status => status.status === 'completed' || status.status === 'failed')) {
        fetchProcessedPodcasts();
      }
    } catch (error) {
      console.error('Error fetching job statuses:', error);
    }
  }, [currentJobs, currentJobId]);

  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;

    const startPolling = () => {
      fetchJobStatuses();
      intervalId = setInterval(fetchJobStatuses, 10000);
    };

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    if (currentJobs.length > 0 || currentJobId) {
      startPolling();
    } else {
      stopPolling();
    }

    return () => {
      stopPolling();
    };
  }, [currentJobs, currentJobId, fetchJobStatuses]);

  const fetchEpisodes = async (url: string) => {
    setIsLoading(true);
    setError('');
    try {
      console.log('Fetching episodes for URL:', `${API_BASE_URL}/episodes`);
      const response = await fetchWithCredentials(`${API_BASE_URL}/episodes`, {
        method: 'POST',
        body: JSON.stringify({ rss_url: url }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        console.error('Error response:', errorData);
        throw new Error(errorData.error || `Failed to fetch episodes: ${response.status}`);
      }
      const data = await response.json();
      console.log('Fetched episodes:', data);
      setEpisodes(data);
    } catch (err) {
      console.error('Error in fetchEpisodes:', err);
      setError('Error fetching episodes: ' + (err as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  const processEpisode = async () => {
    if (selectedEpisode === null) return;
    setError('');
    setIsProcessing(true);

    try {
      const response = await fetchWithCredentials(`${API_BASE_URL}/process`, {
        method: 'POST',
        body: JSON.stringify({ rss_url: rssUrl, episode_index: selectedEpisode }),
      });

      if (!response.ok) throw new Error('Failed to start processing');

      const data = await response.json();
      setCurrentJobId(data.job_id);

      // Set the current job info
      const selectedPodcast = searchResults.find(podcast => podcast.rssUrl === rssUrl);
      const selectedEpisodeInfo = episodes[selectedEpisode];
      setCurrentJobInfo({
        podcastName: selectedPodcast?.name || 'Unknown Podcast',
        episodeTitle: selectedEpisodeInfo?.title || 'Unknown Episode'
      });
    } catch (err) {
      setError('Error processing episode: ' + (err as Error).message);
      setIsProcessing(false);
    }
  };

  const searchPodcasts = async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await fetchWithCredentials(`${API_BASE_URL}/search`, {
        method: 'POST',
        body: JSON.stringify({ query: searchQuery }),
      });
      if (!response.ok) throw new Error('Failed to search podcasts');
      const data = await response.json();
      setSearchResults(data);
    } catch (err) {
      setError('Error searching podcasts: ' + (err as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  const selectPodcast = (rssUrl: string) => {
    console.log(`Selecting podcast with RSS URL: ${rssUrl}`);
    setRssUrl(rssUrl);
    setSearchResults([]);
    fetchEpisodes(rssUrl);
  };

  const handleDownload = (url: string) => {
    // The URL is already encoded, so we don't need to encode it again
    window.open(`${API_BASE_URL}${url}`, '_blank');
  };

  const fetchCurrentJobs = async () => {
    try {
      console.log('Fetching current jobs from:', `${API_BASE_URL}/current_jobs`);
      const response = await fetchWithCredentials(`${API_BASE_URL}/current_jobs`);
      console.log('Response:', response);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      console.log('Current jobs data:', data);
      setCurrentJobs(data);
    } catch (err) {
      console.error('Error fetching current jobs:', err);
      // Don't set an error message for this, as it's not critical for the user experience
    }
  };

  const deleteJob = async (jobId: string) => {
    try {
      const response = await fetchWithCredentials(`${API_BASE_URL}/delete_job/${jobId}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }
      setCurrentJobs((prevJobs) => prevJobs.filter((job) => job.job_id !== jobId));
      if (jobId === currentJobId) {
        setCurrentJobId(null);
      }
    } catch (err) {
      console.error('Error deleting job:', err);
      setError('Error deleting job: ' + (err as Error).message);
    }
  };

  const handleStatusUpdate = (jobId: string, status: JobStatus) => {
    setJobStatuses(prevStatuses => ({
      ...prevStatuses,
      [jobId]: status
    }));
  };

  const handleSearchSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    searchPodcasts();
  };

  const handleEpisodeSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    processEpisode();
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Podcast Content Optimizer</h1>
      </header>
      <main className="App-main">
        <section className="search-section" aria-labelledby="search-heading">
          <h2 id="search-heading">Search for a Podcast</h2>
          <form onSubmit={handleSearchSubmit} className="search-container">
            <label htmlFor="search-input">Search for podcasts</label>
            <input
              id="search-input"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter podcast name"
              aria-describedby="search-description"
            />
            <button type="submit" disabled={isLoading || !searchQuery.trim()}>
              Search
            </button>
          </form>
          <p id="search-description" className="helper-text">Enter a podcast name to search for available episodes.</p>
        </section>

        {searchResults.length > 0 && (
          <section className="search-results" aria-labelledby="results-heading">
            <h2 id="results-heading">Search Results</h2>
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
                  <button onClick={() => selectPodcast(podcast.rssUrl)} className="select-button">
                    Select
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {rssUrl && (
          <section className="selected-podcast" aria-labelledby="selected-heading">
            <h2 id="selected-heading">Selected Podcast</h2>
            <p className="rss-url">{rssUrl}</p>
            <button onClick={() => fetchEpisodes(rssUrl)} disabled={isLoading} className="fetch-button">
              Fetch Episodes
            </button>
          </section>
        )}

        {episodes.length > 0 && (
          <section className="episode-selection" aria-labelledby="episode-heading">
            <h2 id="episode-heading">Select an Episode</h2>
            <form onSubmit={handleEpisodeSubmit} className="episode-container">
              <label htmlFor="episode-select">Choose an episode</label>
              <select
                id="episode-select"
                value={selectedEpisode ?? ''}
                onChange={(e) => setSelectedEpisode(Number(e.target.value))}
                className="episode-select"
                disabled={isProcessing}
              >
                <option value="">Select an episode</option>
                {episodes.map((episode, index) => (
                  <option key={index} value={index}>
                    {episode.title} - {episode.published} ({formatDuration(episode.duration, 'MM:SS')})
                  </option>
                ))}
              </select>
              <button
                type="submit"
                disabled={isLoading || selectedEpisode === null || isProcessing}
                className="process-button"
              >
                {isProcessing ? 'Processing...' : 'Process Episode'}
              </button>
            </form>
          </section>
        )}

        {processedPodcasts.length > 0 ? (
          <section className="processed-podcasts" aria-labelledby="processed-heading">
            <h2 id="processed-heading">Processed Podcasts</h2>
            <ul className="processed-list">
              {processedPodcasts.map((podcast, index) => (
                podcast && podcast.podcast_title && podcast.episode_title ? (
                  <li key={index} className="processed-item">
                    <h3>{podcast.podcast_title} - {podcast.episode_title}</h3>
                    <div className="processed-links">
                      {podcast.edited_url && (
                        <a href={`${API_BASE_URL}${podcast.edited_url}`} target="_blank" rel="noopener noreferrer" className="view-link">
                          Download Edited Audio
                        </a>
                      )}
                      {podcast.transcript_file && (
                        <a href={`${API_BASE_URL}${podcast.transcript_file}`} target="_blank" rel="noopener noreferrer" className="view-link">
                          View Transcript
                        </a>
                      )}
                      {podcast.unwanted_content_file && (
                        <a href={`${API_BASE_URL}${podcast.unwanted_content_file}`} target="_blank" rel="noopener noreferrer" className="view-link">
                          View Unwanted Content
                        </a>
                      )}
                      {podcast.rss_url && (
                        <a href={`${API_BASE_URL}/modified_rss/${encodeURIComponent(podcast.rss_url)}`} target="_blank" rel="noopener noreferrer" className="view-link">
                          View Modified RSS Feed
                        </a>
                      )}
                    </div>
                  </li>
                ) : null
              ))}
            </ul>
          </section>
        ) : (
          <p className="no-podcasts">No processed podcasts available. Process an episode to see results here.</p>
        )}

        {error && (
          <div className="error-message" role="alert">
            {error}
            <button onClick={() => setError('')} className="close-error">×</button>
          </div>
        )}

        {currentJobId && (
          <ProcessingStatus
            jobId={currentJobId}
            status={jobStatuses[currentJobId]}
            onDelete={() => deleteJob(currentJobId)}
            podcastName={currentJobInfo?.podcastName}
            episodeTitle={currentJobInfo?.episodeTitle}
          />
        )}

        {currentJobs.length > 0 && (
          <section className="current-jobs" aria-labelledby="current-jobs-heading">
            <h2 id="current-jobs-heading">Current Jobs</h2>
            {currentJobs.map((job) => (
              <div key={job.job_id} className="job-item">
                <ProcessingStatus
                  jobId={job.job_id}
                  status={jobStatuses[job.job_id]}
                  onDelete={() => deleteJob(job.job_id)}
                  // Note: You might need to store and pass podcast and episode info for each job
                />
              </div>
            ))}
          </section>
        )}

      </main>
    </div>
  );
};

export default App;
