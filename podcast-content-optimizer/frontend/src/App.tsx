import React, { useState, useEffect } from 'react';
import './App.css';

interface Episode {
  number: number;
  title: string;
  published: string;
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

const API_BASE_URL = 'http://localhost:5000/api';

const App: React.FC = () => {
  const [rssUrl, setRssUrl] = useState('');
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [selectedEpisode, setSelectedEpisode] = useState<number | null>(null);
  const [processedPodcasts, setProcessedPodcasts] = useState<ProcessedPodcast[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [processingLogs, setProcessingLogs] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);

  useEffect(() => {
    fetchProcessedPodcasts();
  }, []);

  const fetchProcessedPodcasts = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/processed_podcasts`);
      if (!response.ok) {
        if (response.status === 404) {
          console.warn('Processed podcasts endpoint not found. This feature may not be implemented yet.');
          return;
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setProcessedPodcasts(data);
    } catch (err) {
      console.error('Error fetching processed podcasts:', err);
      setError('Error fetching processed podcasts. This feature may not be implemented yet.');
    }
  };

  const fetchEpisodes = async (url: string) => {
    setIsLoading(true);
    setError('');
    try {
      console.log(`Fetching episodes for RSS URL: ${url}`);
      const response = await fetch(`${API_BASE_URL}/episodes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
    setIsLoading(true);
    setError('');
    setProcessingLogs([]);

    try {
      const response = await fetch(`${API_BASE_URL}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rss_url: rssUrl, episode_index: selectedEpisode }),
      });

      if (!response.ok) throw new Error('Failed to start processing');

      // Start listening to the event stream
      const eventSource = new EventSource(`${API_BASE_URL}/stream?rss_url=${encodeURIComponent(rssUrl)}&episode_index=${selectedEpisode}`);

      eventSource.onmessage = (event) => {
        const log = event.data;
        setProcessingLogs((prevLogs) => [...prevLogs, log]);

        if (log.includes("Processing completed successfully.") || log.includes("Error:")) {
          eventSource.close();
          setIsLoading(false);
          fetchProcessedPodcasts(); // Refresh the list of processed podcasts
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setIsLoading(false);
        setError('Error in processing stream');
      };
    } catch (err) {
      setError('Error processing episode: ' + (err as Error).message);
      setIsLoading(false);
    }
  };

  const getModifiedRssFeed = (rssUrl: string) => {
    return `/api/modified_rss/${encodeURIComponent(rssUrl)}`;
  };

  const searchPodcasts = async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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

  return (
    <div className="App">
      <header className="App-header">
        <h1>Podcast Content Optimizer</h1>
      </header>
      <main className="App-main">
        <section className="search-section" aria-labelledby="search-heading">
          <h2 id="search-heading">Search for a Podcast</h2>
          <div className="search-container">
            <label htmlFor="search-input" className="visually-hidden">Search for podcasts</label>
            <input
              id="search-input"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter podcast name"
              aria-describedby="search-description"
            />
            <button onClick={searchPodcasts} disabled={isLoading || !searchQuery.trim()}>
              Search
            </button>
          </div>
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
            <div className="episode-container">
              <label htmlFor="episode-select" className="visually-hidden">Choose an episode</label>
              <select
                id="episode-select"
                value={selectedEpisode ?? ''}
                onChange={(e) => setSelectedEpisode(Number(e.target.value))}
                className="episode-select"
              >
                <option value="">Select an episode</option>
                {episodes.map((episode, index) => (
                  <option key={index} value={index}>
                    {episode.title} - {episode.published}
                  </option>
                ))}
              </select>
              <button
                onClick={processEpisode}
                disabled={isLoading || selectedEpisode === null}
                className="process-button"
              >
                Process Episode
              </button>
            </div>
          </section>
        )}

        {isLoading && (
          <section className="processing" aria-live="polite">
            <h3>Processing...</h3>
            <ul className="log-list">
              {processingLogs.map((log, index) => (
                <li key={index}>{log}</li>
              ))}
            </ul>
          </section>
        )}

        {processedPodcasts.length > 0 ? (
          <section className="processed-podcasts" aria-labelledby="processed-heading">
            <h2 id="processed-heading">Processed Podcasts</h2>
            <ul className="processed-list">
              {processedPodcasts.map((podcast, index) => (
                <li key={index} className="processed-item">
                  <h3>{podcast.podcast_title} - {podcast.episode_title}</h3>
                  <div className="processed-links">
                    <a href={podcast.edited_url} target="_blank" rel="noopener noreferrer" className="download-link">Download Edited Audio</a>
                    <a href={podcast.transcript_file} target="_blank" rel="noopener noreferrer" className="view-link">View Transcript</a>
                    <a href={podcast.unwanted_content_file} target="_blank" rel="noopener noreferrer" className="view-link">View Unwanted Content</a>
                    <a href={getModifiedRssFeed(podcast.rss_url)} target="_blank" rel="noopener noreferrer" className="view-link">View Modified RSS Feed</a>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ) : (
          <p className="no-podcasts">No processed podcasts available. Process an episode to see results here.</p>
        )}

        {error && <p className="error" role="alert">{error}</p>}
      </main>
    </div>
  );
};

export default App;
