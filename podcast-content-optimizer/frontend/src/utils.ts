export const encodeFilePath = (filePath: string): string => {
  return filePath.split('/').map(segment => encodeURIComponent(segment)).join('/');
};

export const decodeFilePath = (encodedFilePath: string): string => {
  return encodedFilePath.split('/').map(segment => decodeURIComponent(segment)).join('/');
};
