import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { BrandLogo } from '../components/BrandLogo';
import { ThemeToggle } from '../components/ThemeToggle';
import styles from './PublicLayout.module.css';

interface PublicLayoutProps {
  children: ReactNode;
}

export function PublicLayout({ children }: PublicLayoutProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setMenuOpen(false);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [menuOpen]);

  return (
    <div className={styles.wrapper}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div className={styles.brandCell}>
            <Link to="/" className={styles.brandLink} aria-label="AcquireMock home">
              <BrandLogo height={24} />
            </Link>
          </div>

          <div className={styles.navCluster}>
            <nav className={styles.navLinks} aria-label="Primary">
              <Link to="/app/overview" className={styles.navLink}>
                Overview
              </Link>
              <Link to="/app/testing" className={styles.navLink}>
                Playground
              </Link>
              <Link to="/app/webhooks" className={styles.navLink}>
                Webhooks
              </Link>
              <a href="/docs" className={styles.navLink}>
                API Docs
              </a>
            </nav>

            <div className={styles.headerActions}>
              <Link to="/app/testing" className={styles.ctaLink}>
                Create test payment
              </Link>
              <ThemeToggle />
            </div>
          </div>

          <div className={styles.mobileControls}>
            <ThemeToggle />
            <button
              type="button"
              className={styles.menuBtn}
              onClick={() => setMenuOpen((prev) => !prev)}
              aria-expanded={menuOpen}
              aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
            >
              {menuOpen ? <X size={18} strokeWidth={1.75} /> : <Menu size={18} strokeWidth={1.75} />}
            </button>
          </div>
        </div>

        {menuOpen ? (
          <nav className={styles.mobileDrawer} aria-label="Mobile navigation">
            <Link to="/app/overview" className={styles.mobileLink} onClick={() => setMenuOpen(false)}>
              Overview
            </Link>
            <Link to="/app/payments" className={styles.mobileLink} onClick={() => setMenuOpen(false)}>
              Payments
            </Link>
            <Link to="/app/testing" className={styles.mobileLink} onClick={() => setMenuOpen(false)}>
              Playground
            </Link>
            <Link to="/app/webhooks" className={styles.mobileLink} onClick={() => setMenuOpen(false)}>
              Webhooks
            </Link>
            <Link to="/app/settings" className={styles.mobileLink} onClick={() => setMenuOpen(false)}>
              Settings
            </Link>
            <a href="/docs" className={styles.mobileLink}>
              API Docs
            </a>
          </nav>
        ) : null}
      </header>

      <main className={styles.main}>{children}</main>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <div className={styles.footerTop}>
            <div className={styles.footerBrand}>
              <BrandLogo height={22} />
              <p className={styles.disclaimer}>
                Mock payment gateway for development and integration testing only. Never enter real payment card information.
              </p>
            </div>

            <div className={styles.footerColumns}>
              <div className={styles.footerCol}>
                <span className={styles.footerHeading}>Workspace</span>
                <Link to="/app/overview" className={styles.footerLink}>
                  Overview
                </Link>
                <Link to="/app/payments" className={styles.footerLink}>
                  Payments
                </Link>
                <Link to="/app/testing" className={styles.footerLink}>
                  Testing playground
                </Link>
                <Link to="/app/webhooks" className={styles.footerLink}>
                  Webhooks
                </Link>
                <Link to="/app/settings" className={styles.footerLink}>
                  Settings
                </Link>
              </div>
              <div className={styles.footerCol}>
                <span className={styles.footerHeading}>Specification</span>
                <a href="/docs" className={styles.footerLink}>
                  OpenAPI Swagger UI
                </a>
                <a href="/redoc" className={styles.footerLink}>
                  ReDoc Reference
                </a>
                <a href="/health" className={styles.footerLink}>
                  Health Endpoint
                </a>
              </div>
            </div>
          </div>

          <div className={styles.footerBottom}>
            <span>AcquireMock v2.0.0</span>
            <span>Apache License 2.0</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
