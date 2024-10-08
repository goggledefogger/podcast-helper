export function formatDuration(seconds: number, format: 'HH:MM:SS' | 'MM:SS' | 'SS' = 'HH:MM:SS'): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = Math.floor(seconds % 60);

  switch (format) {
    case 'HH:MM:SS':
      return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    case 'MM:SS':
      return `${(hours * 60 + minutes).toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    case 'SS':
      return seconds.toString();
  }
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}
