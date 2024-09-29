import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from 'react-query';
import { fetchWithCredentials } from '../api';
import './PromptEditor.css';
import { useAppContext } from '../contexts/AppContext';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5001';

const PromptEditor: React.FC = () => {
  const { dbData, refreshData } = useAppContext();
  const [geminiPrompt, setGeminiPrompt] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const queryClient = useQueryClient();

  const savePromptMutation = useMutation(
    (newPrompt: string) =>
      fetchWithCredentials(`${API_BASE_URL}/api/prompts`, {
        method: 'POST',
        body: JSON.stringify({ gemini: newPrompt }),
      }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('dbJson');
        refreshData();
        setIsEditing(false);
      },
    }
  );

  useEffect(() => {
    if (dbData && dbData.prompts && dbData.prompts.gemini) {
      setGeminiPrompt(dbData.prompts.gemini);
    }
  }, [dbData]);

  const handleSave = async () => {
    savePromptMutation.mutate(geminiPrompt);
  };

  return (
    <div className="prompt-editor">
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
            <button onClick={handleSave} disabled={savePromptMutation.isLoading}>
              {savePromptMutation.isLoading ? 'Saving...' : 'Save'}
            </button>
            <button onClick={() => setIsEditing(false)} disabled={savePromptMutation.isLoading}>
              Cancel
            </button>
          </>
        ) : (
          <button onClick={() => setIsEditing(true)}>Edit</button>
        )}
      </div>
      {savePromptMutation.isError && <p className="message error">Failed to save prompt. Please try again.</p>}
      {savePromptMutation.isSuccess && <p className="message success">Prompt saved successfully!</p>}
    </div>
  );
};

export default PromptEditor;