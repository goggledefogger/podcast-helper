import React, { useEffect, useState } from 'react';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000/api';

interface ProcessingStatusProps {
  jobId: string;
  onComplete: () => void;
}

interface JobStatus {
  status: 'queued' | 'in_progress' | 'completed' | 'failed';
  progress: number;
  logs: string[];
  current_stage: string;
  start_time: string | null;
  end_time: string | null;
  error?: string;
}

const stageOrder = ['FETCH_EPISODES', 'DOWNLOAD', 'TRANSCRIPTION', 'CONTENT_DETECTION', 'AUDIO_EDITING'];

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ jobId, onComplete }) => {
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/process_status/${jobId}`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Received job status:', data);
        setJobStatus(data);

        if (data.status === 'completed' || data.status === 'failed') {
          onComplete();
        } else {
          setTimeout(fetchStatus, 5000); // Poll every 5 seconds
        }
      } catch (error) {
        console.error('Error fetching processing status:', error);
        setTimeout(fetchStatus, 5000); // Retry after 5 seconds on error
      }
    };

    fetchStatus();
  }, [jobId, onComplete]);

  if (!jobStatus) {
    return <div>Loading status...</div>;
  }

  console.log('Rendering ProcessingStatus with jobStatus:', jobStatus);

  const getStageStatus = (stage: string) => {
    const currentStageIndex = stageOrder.indexOf(jobStatus.current_stage);
    const stageIndex = stageOrder.indexOf(stage);

    if (currentStageIndex === -1 || stageIndex === -1) {
      return 'pending';
    }

    if (stageIndex < currentStageIndex) {
      return 'completed';
    } else if (stageIndex === currentStageIndex) {
      return 'in_progress';
    } else {
      return 'pending';
    }
  };

  return (
    <div className="processing-status">
      <h3>Processing Status: {jobStatus.status}</h3>
      <h4>Current Stage: {jobStatus.current_stage}</h4>
      <div className="processing-stages">
        {stageOrder.map((stage) => (
          <div
            key={stage}
            className={`stage ${getStageStatus(stage)}`}
          >
            <span className="stage-name">{stage}</span>
            <span className="stage-status">
              {getStageStatus(stage)}
            </span>
          </div>
        ))}
      </div>
      <p>Progress: {jobStatus.progress}%</p>
      {jobStatus.start_time && <p>Started: {new Date(jobStatus.start_time).toLocaleString()}</p>}
      {jobStatus.end_time && <p>Ended: {new Date(jobStatus.end_time).toLocaleString()}</p>}
      {jobStatus.error && (
        <div className="error">
          <h4>Error:</h4>
          <p>{jobStatus.error}</p>
        </div>
      )}
      <div className="log-container">
        <h4>Processing Logs:</h4>
        {jobStatus.logs.map((log, index) => (
          <div key={index} className="log-entry">{log}</div>
        ))}
      </div>
    </div>
  );
};

export default ProcessingStatus;
