import { initializeApp } from 'firebase/app';
import { getStorage, ref, getDownloadURL } from 'firebase/storage';
import { API_BASE_URL } from './api';

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

export const getProcessedPodcasts = async (): Promise<ProcessedPodcast[]> => {
  try {
    const url = await getFileUrl('db.json');
    if (url) {
      const response = await fetch(url);
      const data = await response.json();
      return data.processed_podcasts as ProcessedPodcast[];
    }
    return [];
  } catch (error) {
    console.error('Error fetching processed podcasts:', error);
    return [];
  }
};

export const getFileUrl = async (path: string) => {
  try {
    // First, try to make the file public
    const response = await fetch(`${API_BASE_URL}/api/make_file_public`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ file_path: path }),
    });

    if (response.ok) {
      const data = await response.json();
      return data.public_url;
    } else {
      // If making public fails, fall back to getDownloadURL
      const fileRef = ref(storage, path);
      return await getDownloadURL(fileRef);
    }
  } catch (error) {
    console.error('Error getting file URL:', error);
    return null;
  }
};
