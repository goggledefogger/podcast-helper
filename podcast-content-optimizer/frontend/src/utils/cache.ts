interface CacheItem<T> {
  data: T;
  timestamp: number;
}

const cache: { [key: string]: CacheItem<any> } = {};

export function setCache<T>(key: string, data: T, expirationTime: number = 60000): void {
  cache[key] = { data, timestamp: Date.now() + expirationTime };
}

export function getCache<T>(key: string): T | null {
  const item = cache[key];
  if (item && item.timestamp > Date.now()) {
    return item.data;
  }
  return null;
}

export function removeCache(key: string): void {
  delete cache[key];
}