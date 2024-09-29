import React from 'react';
import './ProcessingStatus.css';

const STAGES = [
  'INITIALIZATION',
  'FETCH_EPISODES',
  'DOWNLOAD',
  'TRANSCRIPTION',
  'CONTENT_DETECTION',  // Changed from 'CONTENT_ANALYSIS'
  'AUDIO_EDITING',
  'RSS_MODIFICATION',
  'COMPLETION'
];

interface ProcessingStatusProps {
  jobId: string;
  status: JobStatus | undefined;
  onDelete?: () => void;
  podcastName?: string;
  episodeTitle?: string;
}

interface JobStatus {
  status: 'queued' | 'in_progress' | 'completed' | 'failed';
  current_stage: string;
  progress: number;
  message: string;
  timestamp: number;
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ jobId, status, onDelete, podcastName, episodeTitle }) => {
  if (!status) {
    return <div className="processing-status loading">Loading status...</div>;
  }

  const getStageStatus = (stage: string) => {
    const currentStageIndex = STAGES.indexOf(status.current_stage);
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
      {podcastName && episodeTitle && (
        <div className="podcast-info">
          <h3>{podcastName}</h3>
          <h4>{episodeTitle}</h4>
        </div>
      )}
      <h3 className="status-title">Processing Status: <span className={`status-value ${status.status}`}>{status.status}</span></h3>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${status.progress}%` }}></div>
      </div>
      <p className="current-stage">Current Stage: <span className="stage-value">{status.current_stage}</span></p>
      <div className="processing-stages">
        {STAGES.map((stage) => (
          <div
            key={stage}
            className={`stage ${getStageStatus(stage)}`}
          >
            <span className="stage-name">{stage}</span>
            <span className="stage-icon"></span>
          </div>
        ))}
      </div>
      <p className="status-message">{status.message}</p>
      <p className="timestamp">Last Updated: {new Date(status.timestamp * 1000).toLocaleString()}</p>
      {onDelete && (
        <button onClick={onDelete} className="delete-job-button">
          Delete Job
        </button>
      )}
    </div>
  );
};

export default ProcessingStatus;
