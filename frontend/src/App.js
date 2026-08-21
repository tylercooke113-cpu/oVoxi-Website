import './App.css';
import { useEffect, useState, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Toaster } from 'sonner';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import HomePage from './pages/HomePage';
import ContactPage from './pages/ContactPage';
import UploadPage from './pages/UploadPage';
import ApplyPage from './pages/ApplyPage';
import ApplyTracksPage from './pages/ApplyTracksPage';
import AdminPage from './pages/AdminPage';
import SignUpPage from './pages/SignUpPage';
import LoginPage from './pages/LoginPage';
import VaultPage from './pages/VaultPage';
import AppealPage from './pages/AppealPage';

const NEW_MARKETING = process.env.REACT_APP_NEW_MARKETING === 'true';
const MarketingPage = lazy(() => import('./marketing/MarketingPage'));

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

const AUTH_PATHS = ['/signup', '/login', '/vault', '/appeal'];

function AppContent() {
  const { pathname } = useLocation();
  const isMarketingHome = NEW_MARKETING && pathname === '/';

 return (
  <>
    <ScrollToTop />
    {!isMarketingHome && <Header />}
      <main>
        <Routes>
          <Route
            path='/'
            element={NEW_MARKETING
              ? <Suspense fallback={null}><MarketingPage /></Suspense>
              : <HomePage />}
          />
          <Route path='/contact' element={<ContactPage />} />
          <Route path='/artist-upload' element={<Navigate to='/signup' replace />} />
          <Route path='/upload' element={<UploadPage />} />
          <Route path='/apply' element={<ApplyPage />} />
          <Route path='/apply/tracks' element={<ApplyTracksPage />} />
          <Route path='/admin' element={<AdminPage />} />
          <Route path='/signup/*' element={<SignUpPage />} />
          <Route path='/login/*' element={<LoginPage />} />
          <Route path='/vault' element={<VaultPage />} />
          <Route path='/appeal/:submissionId' element={<AppealPage />} />
        </Routes>
      </main>
      {!isMarketingHome && <Footer />}
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
