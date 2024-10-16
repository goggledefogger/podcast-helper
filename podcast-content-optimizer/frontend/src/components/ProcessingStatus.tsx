import React from 'react';
import Loader from './Loader';
import './ProcessingStatus.css';

const STAGES = [
  'INITIALIZATION',
  'FETCH_EPISODES',
  'DOWNLOAD',
  'TRANSCRIPTION',
  'CONTENT_DETECTION',
  'AUDIO_EDITING',
  'RSS_MODIFICATION',
  'COMPLETION'
];

interface JobInfo {
  podcastName: string;
  episodeTitle: string;
  rssUrl: string;
}

interface ProcessingStatusProps {
  jobId: string;
  status: JobStatus | undefined;
  onDelete?: () => void;
  jobInfo?: JobInfo;
  podcastImageUrl?: string;
}

interface JobStatus {
  status: 'queued' | 'in_progress' | 'completed' | 'failed';
  current_stage: string;
  progress: number;
  message: string;
  timestamp: number;
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ jobId, status, onDelete, jobInfo, podcastImageUrl }) => {
  if (!jobInfo) {
    return <Loader />;
  }

  // Use a default status if the actual status is not available yet
  const currentStatus: JobStatus = status || {
    status: 'queued',
    current_stage: 'INITIALIZATION',
    progress: 0,
    message: 'Initializing job...',
    timestamp: Date.now() / 1000
  };

  const getStageStatus = (stage: string) => {
    const currentStageIndex = STAGES.indexOf(currentStatus.current_stage);
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
      <div className="podcast-info">
        {podcastImageUrl && <img src={podcastImageUrl} alt={jobInfo.podcastName} className="podcast-image" />}
        <div className="podcast-details">
          <h3>{jobInfo.podcastName || 'Unknown Podcast'}</h3>
          {jobInfo.rssUrl && <p className="rss-url">{jobInfo.rssUrl}</p>}
          <h4>{jobInfo.episodeTitle || 'Unknown Episode'}</h4>
        </div>
      </div>
      <h3 className="status-title">Processing Status: <span className={`status-value ${currentStatus.status}`}>{currentStatus.status}</span></h3>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${currentStatus.progress}%` }}></div>
      </div>
      <p className="current-stage">Current Stage: <span className="stage-value">{currentStatus.current_stage}</span></p>
      <div className="processing-stages">
        <div className="stage-line"></div>
        {STAGES.map((stage) => (
          <div
            key={stage}
            className={`stage ${getStageStatus(stage)}`}
          >
            <span className="stage-icon"></span>
            <span className="stage-name">{stage}</span>
          </div>
        ))}
      </div>
      <p className="status-message">{currentStatus.message}</p>
      <p className="timestamp">Last Updated: {new Date(currentStatus.timestamp * 1000).toLocaleString()}</p>
      {onDelete && (
        <button onClick={onDelete} className="delete-job-button">
          Delete Job
        </button>
      )}
    </div>
  );
};

export default ProcessingStatus;
