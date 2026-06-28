import { useEffect } from 'react';

const ArtistUploadPage = () => {
  useEffect(() => {
    window.location.replace('/signup');
  }, []);
  return null;
};

export default ArtistUploadPage;
