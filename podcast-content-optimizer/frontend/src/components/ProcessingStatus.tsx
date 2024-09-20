import React from 'react';

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
}

interface JobStatus {
  status: 'queued' | 'in_progress' | 'completed' | 'failed';
  current_stage: string;
  progress: number;
  message: string;
  timestamp: number;
}

const ProcessingStatus: React.FC<ProcessingStatusProps> = ({ jobId, status, onDelete }) => {
  if (!status) {
    return <div>Loading status...</div>;
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
      <h3>Processing Status: {status.status}</h3>
      <h4>Current Stage: {status.current_stage}</h4>
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
      <p>Progress: {status.progress}%</p>
      <p>Last Updated: {new Date(status.timestamp * 1000).toLocaleString()}</p>
      {status.message && <p>Message: {status.message}</p>}
      {onDelete && (
        <button onClick={onDelete} className="delete-job-button">
          Delete Job
        </button>
      )}
    </div>
  );
};

export default ProcessingStatus;
