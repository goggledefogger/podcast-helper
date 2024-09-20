import React, { useEffect, useState } from 'react';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000/api';

const STAGES = [
  'INITIALIZATION',
  'FETCH_EPISODES',
  'DOWNLOAD',
  'TRANSCRIPTION',
  'CONTENT_ANALYSIS',
  'AUDIO_EDITING',
  'RSS_MODIFICATION',
  'COMPLETION'
];

interface ProcessingStatusProps {
  jobId: string;
  onComplete: () => void;
}

interface JobStatus {
  status: 'queued' | 'in_progress' | 'completed' | 'failed';
  current_stage: string;
  progress: number;
  message: string;
  timestamp: number;
}

interface JobLog {
  stage: string;
  message: string;
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ jobId, onComplete }) => {
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [jobLogs, setJobLogs] = useState<JobLog[]>([]);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/process_status/${jobId}`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setJobStatus(data.status);
        setJobLogs(data.logs);

        if (data.status.status === 'completed' || data.status.status === 'failed') {
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
    const currentStageIndex = STAGES.indexOf(jobStatus.current_stage);
    const stageIndex = STAGES.indexOf(stage);

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
        {STAGES.map((stage) => (
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
      <p>Last Updated: {new Date(jobStatus.timestamp * 1000).toLocaleString()}</p>
      {jobStatus.message && <p>Message: {jobStatus.message}</p>}
      <div className="log-container">
        <h4>Processing Logs:</h4>
        {jobLogs.map((log, index) => (
          <div key={index} className="log-entry">
            <strong>{log.stage}:</strong> {log.message}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProcessingStatus;
