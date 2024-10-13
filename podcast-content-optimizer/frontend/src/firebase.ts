import { initializeApp } from 'firebase/app';
import { getStorage, ref, getDownloadURL } from 'firebase/storage';

const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY,
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID,
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.REACT_APP_FIREBASE_APP_ID
};

const app = initializeApp(firebaseConfig);
export const storage = getStorage(app);

export interface ProcessedPodcast {
  podcast_title: string;
  episode_title: string;
  edited_url: string;
  transcript_file: string;
  unwanted_content_file: string;
  rss_url: string; // Add this line
}

export const getProcessedPodcasts = async (): Promise<{
  processed: Record<string, ProcessedPodcast[]>,
  autoProcessed: string[],
  prompts: Record<string, string>,
  podcastInfo: Record<string, { name: string; imageUrl: string }>
}> => {
  try {
    const url = await getFileUrl('db.json');
    if (url) {
      const response = await fetch(url);
      const data = await response.json();
      console.log('Fetched data:', data); // Add this line for debugging
      return {
        processed: data.processed_podcasts || {},
        autoProcessed: data.auto_processed_podcasts || [],
        prompts: data.prompts || {},
        podcastInfo: data.podcast_info || {}
      };
    }
    return { processed: {}, autoProcessed: [], prompts: {}, podcastInfo: {} };
  } catch (error) {
    console.error('Error fetching processed podcasts:', error);
    return { processed: {}, autoProcessed: [], prompts: {}, podcastInfo: {} };
  }
};

export const getFileUrl = async (path: string): Promise<string | null> => {
  try {
    return await getDownloadURL(ref(storage, path));
  } catch (error) {
    console.error('Error getting file URL:', error);
    return null;
  }
};
