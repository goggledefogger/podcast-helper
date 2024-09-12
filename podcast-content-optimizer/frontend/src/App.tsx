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
      <main>
        <div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search for podcasts"
          />
          <button onClick={searchPodcasts} disabled={isLoading}>
            Search
          </button>
        </div>

        {searchResults.length > 0 && (
          <div>
            <h2>Search Results</h2>
            <ul>
              {searchResults.map((podcast) => (
                <li key={podcast.uuid}>
                  <h3>{podcast.name}</h3>
                  <p>{podcast.description}</p>
                  {podcast.imageUrl && <img src={podcast.imageUrl} alt={podcast.name} style={{maxWidth: '100px'}} />}
                  <button onClick={() => selectPodcast(podcast.rssUrl)}>Select</button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {rssUrl && (
          <div>
            <h2>Selected Podcast RSS URL</h2>
            <p>{rssUrl}</p>
            <button onClick={() => fetchEpisodes(rssUrl)} disabled={isLoading}>
              Fetch Episodes
            </button>
          </div>
        )}

        {episodes.length > 0 && (
          <div>
            <h2>Select an Episode</h2>
            <select
              value={selectedEpisode ?? ''}
              onChange={(e) => setSelectedEpisode(Number(e.target.value))}
            >
              <option value="">Select an episode</option>
              {episodes.map((episode, index) => (
                <option key={index} value={index}>
                  {episode.title} - {episode.published}
                </option>
              ))}
            </select>
            <button onClick={processEpisode} disabled={isLoading || selectedEpisode === null}>
              Process Episode
            </button>
          </div>
        )}

        {isLoading && (
          <div>
            <h3>Processing...</h3>
            <ul>
              {processingLogs.map((log, index) => (
                <li key={index}>{log}</li>
              ))}
            </ul>
          </div>
        )}

        {processedPodcasts.length > 0 ? (
          <div>
            <h2>Processed Podcasts</h2>
            <ul>
              {processedPodcasts.map((podcast, index) => (
                <li key={index}>
                  <h3>{podcast.podcast_title} - {podcast.episode_title}</h3>
                  <p>Edited Audio: <a href={podcast.edited_url} target="_blank" rel="noopener noreferrer">Download</a></p>
                  <p>Transcript: <a href={podcast.transcript_file} target="_blank" rel="noopener noreferrer">View</a></p>
                  <p>Unwanted Content: <a href={podcast.unwanted_content_file} target="_blank" rel="noopener noreferrer">View</a></p>
                  <p>Modified RSS Feed: <a href={getModifiedRssFeed(podcast.rss_url)} target="_blank" rel="noopener noreferrer">View</a></p>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p>No processed podcasts available. Process an episode to see results here.</p>
        )}

        {error && <p className="error">{error}</p>}
      </main>
    </div>
  );
};

export default App;
