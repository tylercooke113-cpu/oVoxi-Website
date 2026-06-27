import './App.css';
import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import PasswordGate from './components/PasswordGate';
import { Toaster } from 'sonner';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import HomePage from './pages/HomePage';
import ArtistsPage from './pages/ArtistsPage';
import AboutPage from './pages/AboutPage';
import ContactPage from './pages/ContactPage';
import UploadPage from './pages/UploadPage';
import ApplyPage from './pages/ApplyPage';
import ApplyTracksPage from './pages/ApplyTracksPage';
import AdminPage from './pages/AdminPage';
import SignUpPage from './pages/SignUpPage';
import LoginPage from './pages/LoginPage';
import VaultPage from './pages/VaultPage';

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

const SESSION_KEY = 'ovoxi_access_granted';
const AUTH_PATHS = ['/signup', '/login', '/vault'];

function AppContent() {
  const { pathname } = useLocation();
  const [unlocked, setUnlocked] = useState(
    () => sessionStorage.getItem(SESSION_KEY) === '1'
  );

  const isAuthRoute = AUTH_PATHS.some(p => pathname.startsWith(p));

  return (
    <>
      <ScrollToTop />
      {!unlocked && !isAuthRoute && (
        <PasswordGate onUnlock={() => {
          sessionStorage.setItem(SESSION_KEY, '1');
          setUnlocked(true);
        }} />
      )}
      <Header />
      <main>
        <Routes>
          <Route path='/' element={<HomePage />} />
          <Route path='/artists' element={<ArtistsPage />} />
          <Route path='/about' element={<AboutPage />} />
          <Route path='/contact' element={<ContactPage />} />
          <Route path='/artist-upload' element={<Navigate to='/signup' replace />} />
          <Route path='/upload' element={<UploadPage />} />
          <Route path='/apply' element={<ApplyPage />} />
          <Route path='/apply/tracks' element={<ApplyTracksPage />} />
          <Route path='/admin' element={<AdminPage />} />
          <Route path='/signup/*' element={<SignUpPage />} />
          <Route path='/login/*' element={<LoginPage />} />
          <Route path='/vault' element={<VaultPage />} />
        </Routes>
      </main>
      <Footer />
      <Toaster theme='dark' position='bottom-right' richColors />
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
