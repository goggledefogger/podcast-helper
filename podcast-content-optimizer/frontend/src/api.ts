export const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || window.location.origin;

export const fetchWithCredentials = (url: string, options: RequestInit = {}) => {
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

export const fetchEpisodes = async (rssUrl: string) => {
  const response = await fetchWithCredentials(`${API_BASE_URL}/api/episodes`, {
    method: 'POST',
    body: JSON.stringify({ rss_url: rssUrl }),
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.error || `Failed to fetch episodes: ${response.status}`);
  }
  return await response.json();
};

export const processEpisode = async (rssUrl: string, episodeIndex: number) => {
  const response = await fetchWithCredentials(`${API_BASE_URL}/api/process`, {
    method: 'POST',
    body: JSON.stringify({ rss_url: rssUrl, episode_index: episodeIndex }),
  });
  if (!response.ok) {
    throw new Error('Failed to start processing');
  }
  return await response.json();
};

export const searchPodcasts = async (query: string) => {
  const response = await fetchWithCredentials(`${API_BASE_URL}/api/search`, {
    method: 'POST',
    body: JSON.stringify({ query }),
  });
  if (!response.ok) {
    throw new Error('Failed to search podcasts');
  }
  return await response.json();
};

export const fetchCurrentJobs = async () => {
  const response = await fetchWithCredentials(`${API_BASE_URL}/api/current_jobs`);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return await response.json();
};

export const deleteJob = async (jobId: string) => {
  const response = await fetchWithCredentials(`${API_BASE_URL}/api/delete_job/${jobId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
};

export interface JobStatus {
  status: 'queued' | 'in_progress' | 'completed' | 'failed';
  current_stage: string;
  progress: number;
  message: string;
  timestamp: number;
}

export const fetchJobStatuses = async (jobIds: string[]): Promise<Record<string, JobStatus>> => {
  const response = await fetchWithCredentials(`${API_BASE_URL}/api/batch_process_status`, {
    method: 'POST',
    body: JSON.stringify({ job_ids: jobIds }),
  });
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return await response.json();
};

export const deleteProcessedPodcast = async (podcastTitle: string, episodeTitle: string) => {
  const response = await fetchWithCredentials(`${API_BASE_URL}/api/delete_processed_podcast`, {
    method: 'POST',
    body: JSON.stringify({ podcast_title: podcastTitle, episode_title: episodeTitle }),
  });
  if (!response.ok) {
    throw new Error('Failed to delete podcast');
  }
  return await response.json();
};

export const enableAutoProcessing = async (rssUrl: string): Promise<void> => {
  const response = await fetchWithCredentials(`${API_BASE_URL}/api/auto_process`, {
    method: 'POST',
    body: JSON.stringify({ rss_url: rssUrl }),
  });

  if (!response.ok) {
    throw new Error('Failed to enable auto-processing');
  }
  return await response.json();
};

export const fetchAutoProcessedPodcasts = async (): Promise<string[]> => {
  const response = await fetchWithCredentials(`${API_BASE_URL}/api/auto_processed_podcasts`);
  if (!response.ok) {
    throw new Error('Failed to fetch auto-processed podcasts');
  }
  return await response.json();
};
