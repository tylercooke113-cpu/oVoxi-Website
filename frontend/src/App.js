import "./App.css";
import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import PasswordGate from "./components/PasswordGate";
import { Toaster } from "sonner";
import { Header } from "./components/Header";
import { Footer } from "./components/Footer";
import HomePage from "./pages/HomePage";
import ArtistsPage from "./pages/ArtistsPage";
import AboutPage from "./pages/AboutPage";
import ContactPage from "./pages/ContactPage";
import UploadPage from "./pages/UploadPage";
import SignUpPage from "./pages/SignUpPage";
import LoginPage from "./pages/LoginPage";
import VaultPage from "./pages/VaultPage";
import ApplyPage from "./pages/ApplyPage";
import ApplyTracksPage from "./pages/ApplyTracksPage";
import AdminPage from "./pages/AdminPage";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

const SESSION_KEY = "ovoxi_access_granted";

function App() {
  const [unlocked, setUnlocked] = useState(
    () => sessionStorage.getItem(SESSION_KEY) === "1"
  );

  const isAuthRoute = ['/signup', '/login', '/vault'].some(path =>
    window.location.pathname.startsWith(path)
  );

  return (
    <div className="App min-h-screen bg-ink">
      {!unlocked && !isAuthRoute && <PasswordGate onUnlock={() => setUnlocked(true)} />}
      <BrowserRouter>
        <ScrollToTop />
        <Header />
        <main>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/artists" element={<ArtistsPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/contact" element={<ContactPage />} />
            <Route path="/artist-upload" element={<Navigate to="/signup" replace />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/signup" element={<SignUpPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/vault" element={<VaultPage />} />
            <Route path="/apply" element={<ApplyPage />} />
            <Route path="/apply/tracks" element={<ApplyTracksPage />} />
            <Route path="/admin" element={<AdminPage />} />
          </Routes>
        </main>
        <Footer />
        <Toaster theme="dark" position="bottom-right" richColors />
      </BrowserRouter>
    </div>
  );
}

export default App;
