import { Outlet } from 'react-router-dom';
import MainNavbar from './MainNavbar';
import Footer from './Footer';

export default function MainLayout() {
  return (
    <div className="d-flex flex-column min-vh-100">
      <MainNavbar />
      <main className="container-fluid py-3 flex-grow-1" id="main-content">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
