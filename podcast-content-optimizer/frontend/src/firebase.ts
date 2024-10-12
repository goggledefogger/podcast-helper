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
  rss_url: string;
  edited_url: string;
  transcript_file: string;
  unwanted_content_file: string;
}

export const getProcessedPodcasts = async (): Promise<{ processed: ProcessedPodcast[], autoProcessed: string[], prompts: Record<string, string> }> => {
  try {
    const url = await getFileUrl('db.json');
    if (url) {
      const response = await fetch(url);
      const data = await response.json();
      return {
        processed: data.processed_podcasts as ProcessedPodcast[],
        autoProcessed: data.auto_processed_podcasts as string[],
        prompts: data.prompts || {}
      };
    }
    return { processed: [], autoProcessed: [], prompts: {} };
  } catch (error) {
    console.error('Error fetching processed podcasts:', error);
    return { processed: [], autoProcessed: [], prompts: {} };
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
