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
        setJobStatus(data);

        if (data.status === 'completed' || data.status === 'failed') {
          onComplete();
        } else {
          setTimeout(fetchStatus, 20000); // Poll every 20 seconds
        }
      } catch (error) {
        console.error('Error fetching processing status:', error);
        setJobStatus({
          status: 'failed',
          progress: 0,
          logs: [],
          current_stage: 'Error',
          start_time: null,
          end_time: null,
          error: `Failed to fetch status: ${(error as Error).message}`
        });
        setTimeout(fetchStatus, 20000); // Retry after 20 seconds
      }
    };

    fetchStatus();
  }, [jobId, onComplete]);

  return (
    <div className="processing-status">
      <h3>Processing Status: {jobStatus?.status}</h3>
      <h4>Current Stage: {jobStatus?.current_stage}</h4>
      <p>Progress: {jobStatus?.progress}%</p>
      {jobStatus?.start_time && <p>Started: {new Date(jobStatus.start_time).toLocaleString()}</p>}
      {jobStatus?.end_time && <p>Ended: {new Date(jobStatus.end_time).toLocaleString()}</p>}
      {jobStatus?.error && (
        <div className="error">
          <h4>Error:</h4>
          <p>{jobStatus.error}</p>
        </div>
      )}
      <div className="log-container">
        <h4>Processing Logs:</h4>
        {jobStatus?.logs.map((log, index) => (
          <div key={index} className="log-entry">{log}</div>
        ))}
      </div>
    </div>
  );
};

export default ProcessingStatus;
