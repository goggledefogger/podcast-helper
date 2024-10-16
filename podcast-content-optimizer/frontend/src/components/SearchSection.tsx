import React from 'react';
import './SearchSection.css';

interface SearchSectionProps {
  openSearchModal: () => void;
}

const SearchSection: React.FC<SearchSectionProps> = ({ openSearchModal }) => {
  return (
    <section className="search-section" aria-labelledby="search-heading">
      <h2 id="search-heading">Find and Process a Podcast</h2>
      <button onClick={openSearchModal} className="open-search-button">
        Search for Podcasts
      </button>
    </section>
  );
};

export default SearchSection;
