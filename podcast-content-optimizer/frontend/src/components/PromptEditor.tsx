import React, { useState, useEffect } from 'react';
import { fetchWithCredentials } from '../api';
import { getProcessedPodcasts } from '../firebase';
import './PromptEditor.css'; // Create this file for PromptEditor-specific styles

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5001';

const PromptEditor: React.FC = () => {
  const [geminiPrompt, setGeminiPrompt] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchPrompts();
  }, []);

  const fetchPrompts = async () => {
    try {
      const { prompts } = await getProcessedPodcasts();
      setGeminiPrompt(prompts.gemini || '');
    } catch (error) {
      console.error('Error fetching prompts:', error);
      setMessage('Failed to load prompt. Please try again.');
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setMessage('');
    try {
      const response = await fetchWithCredentials(`${API_BASE_URL}/api/prompts`, {
        method: 'POST',
        body: JSON.stringify({
          gemini: geminiPrompt
        }),
      });
      if (!response.ok) {
        throw new Error('Failed to save prompt');
      }
      setMessage('Prompt saved successfully!');
      setIsEditing(false);
    } catch (error) {
      console.error('Error saving prompt:', error);
      setMessage('Failed to save prompt. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="prompt-editor prompt-editor-section">
      <h2>Edit Gemini Prompt</h2>
      <div className="prompt-container">
        {isEditing ? (
          <textarea
            value={geminiPrompt}
            onChange={(e) => setGeminiPrompt(e.target.value)}
            rows={10}
            cols={50}
          />
        ) : (
          <pre className="prompt-display">{geminiPrompt}</pre>
        )}
      </div>
      <div className="button-container">
        {isEditing ? (
          <>
            <button onClick={handleSave} disabled={isSaving}>
              {isSaving ? 'Saving...' : 'Save'}
            </button>
            <button onClick={() => setIsEditing(false)} disabled={isSaving}>
              Cancel
            </button>
          </>
        ) : (
          <button onClick={() => setIsEditing(true)}>Edit</button>
        )}
      </div>
      {message && <p className={`message ${message.includes('success') ? 'success' : 'error'}`}>{message}</p>}
    </div>
  );
};

export default PromptEditor;
