import React from 'react';
import Modal from 'react-modal';
import { useSearch, SearchResult } from '../hooks/useSearch';
import Loader from './Loader';
import './SearchModal.css';

interface SearchModalProps {
  isOpen: boolean;
  onRequestClose: () => void;
  onNotification: (message: string) => void;
}

const SearchModal: React.FC<SearchModalProps> = ({ isOpen, onRequestClose, onNotification }) => {
  const {
    searchQuery,
    setSearchQuery,
    searchResults,
    isSearchLoading,
    handleSearch,
    handleEnableAutoProcessingClick,
    autoPodcasts
  } = useSearch();

  const handleClose = () => {
    onRequestClose();
    setSearchQuery('');
  };

  const handleEnableAutoProcessing = async (result: SearchResult) => {
    try {
      const message = await handleEnableAutoProcessingClick(result);
      onNotification(message);
    } catch (error) {
      // Error is already set in the context
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onRequestClose={handleClose}
      contentLabel="Search Podcasts"
      className="search-modal"
      overlayClassName="search-modal-overlay"
    >
      <h2>Search Podcasts</h2>
      <form onSubmit={(e) => { e.preventDefault(); handleSearch(); }} className="search-form">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Enter podcast name"
          className="search-input"
        />
        <button type="submit" disabled={isSearchLoading} className="search-button">
          {isSearchLoading ? 'Searching...' : 'Search'}
        </button>
      </form>
      {isSearchLoading ? (
        <Loader />
      ) : (
        <div className="search-results">
          {searchResults.map((result) => (
            <div key={result.uuid} className="search-result">
              <img src={result.imageUrl} alt={result.name} className="search-result-image" />
              <div className="search-result-content">
                <h3>{result.name}</h3>
                <p>{result.description}</p>
                <div className="search-result-actions">
                  {autoPodcasts.some(podcast => podcast.rss_url === result.rssUrl) ? (
                    <span className="auto-processing-badge">Auto-processing enabled</span>
                  ) : (
                    <button
                      onClick={() => handleEnableAutoProcessing(result)}
                      className="enable-auto-processing-button"
                    >
                      Enable Auto-processing
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      <button onClick={handleClose} className="close-modal-button">Close</button>
    </Modal>
  );
};

export default SearchModal;
