import { useState, useCallback } from 'react';
import { searchPodcasts } from '../api';
import { usePodcastContext } from '../contexts/PodcastContext';

export interface SearchResult {
  uuid: string;
  name: string;
  description: string;
  imageUrl: string;
  rssUrl: string;
}

export const useSearch = () => {
  const { autoPodcasts, handleEnableAutoProcessing, setError, setPodcastInfo } = usePodcastContext();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearchLoading, setIsSearchLoading] = useState(false);

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;
    setIsSearchLoading(true);
    setError('');
    try {
      const results = await searchPodcasts(searchQuery);
      setSearchResults(results);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsSearchLoading(false);
    }
  }, [searchQuery, setError]);

  const handleEnableAutoProcessingClick = async (result: SearchResult) => {
    try {
      await handleEnableAutoProcessing(result);
      setPodcastInfo(prev => ({
        ...prev,
        [result.rssUrl]: { name: result.name, imageUrl: result.imageUrl }
      }));
      return `Auto-processing enabled for ${result.name}`;
    } catch (error) {
      setError((error as Error).message);
      throw error;
    }
  };

  return {
    searchQuery,
    setSearchQuery,
    searchResults,
    isSearchLoading,
    handleSearch,
    handleEnableAutoProcessingClick,
    autoPodcasts
  };
};
