import React, { useState, useEffect } from 'react';
import { fetchWithCredentials } from '../api';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5001';

const PromptEditor: React.FC = () => {
  const [openaiPrompt, setOpenaiPrompt] = useState('');
  const [geminiPrompt, setGeminiPrompt] = useState('');

  useEffect(() => {
    fetchPrompts();
  }, []);

  const fetchPrompts = async () => {
    try {
      const response = await fetchWithCredentials(`${API_BASE_URL}/api/prompts`);
      if (!response.ok) {
        throw new Error('Failed to fetch prompts');
      }
      const data = await response.json();
      setOpenaiPrompt(data.openai);
      setGeminiPrompt(data.gemini);
    } catch (error) {
      console.error('Error fetching prompts:', error);
    }
  };

  const handleSave = async () => {
    try {
      const response = await fetchWithCredentials(`${API_BASE_URL}/api/prompts`, {
        method: 'POST',
        body: JSON.stringify({
          openai: openaiPrompt,
          gemini: geminiPrompt
        }),
      });
      if (!response.ok) {
        throw new Error('Failed to save prompts');
      }
      alert('Prompts saved successfully!');
    } catch (error) {
      console.error('Error saving prompts:', error);
      alert('Failed to save prompts. Please try again.');
    }
  };

  return (
    <div className="prompt-editor">
      <h2>Edit LLM Prompts</h2>
      <div>
        <h3>OpenAI Prompt</h3>
        <textarea
          value={openaiPrompt}
          onChange={(e) => setOpenaiPrompt(e.target.value)}
          rows={5}
          cols={50}
        />
      </div>
      <div>
        <h3>Gemini Prompt</h3>
        <textarea
          value={geminiPrompt}
          onChange={(e) => setGeminiPrompt(e.target.value)}
          rows={5}
          cols={50}
        />
      </div>
      <button onClick={handleSave}>Save Prompts</button>
    </div>
  );
};

export default PromptEditor;
