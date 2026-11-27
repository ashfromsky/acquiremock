import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import {
  Activity,
  CreditCard,
  ExternalLink,
  FlaskConical,
  Menu,
  Settings,
  Webhook,
  X,
} from 'lucide-react';
import { BrandLogo } from '../components/BrandLogo';
import { ThemeToggle } from '../components/ThemeToggle';
import { useAuthSession } from '../hooks/useAuth';
import styles from './AppLayout.module.css';

interface Crumb {
  label: string;
  to?: string;
}

interface AppLayoutProps {
  title: string;
  subtitle?: string;
  breadcrumbs: Crumb[];
  actions?: ReactNode;
  children: ReactNode;
}

const WORKSPACE_NAV = [
  { to: '/app/overview', label: 'Overview', icon: Activity },
  { to: '/app/payments', label: 'Payments', icon: CreditCard },
  { to: '/app/testing', label: 'Testing', icon: FlaskConical },
  { to: '/app/webhooks', label: 'Webhooks', icon: Webhook },
];

export function AppLayout({
  title,
  subtitle,
  breadcrumbs,
  actions,
  children,
}: AppLayoutProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useLocation();
  const { data: session } = useAuthSession();

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!drawerOpen) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setDrawerOpen(false);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [drawerOpen]);

  const sidebarContent = (
    <div className={styles.sidebarInner}>
      <div className={styles.sidebarTop}>
        <Link to="/" className={styles.brandLink} aria-label="AcquireMock public homepage">
          <BrandLogo height={22} />
        </Link>
        <button
          type="button"
          className={styles.drawerClose}
          onClick={() => setDrawerOpen(false)}
          aria-label="Close navigation"
        >
          <X size={18} strokeWidth={1.75} />
        </button>
      </div>

      <div className={styles.navSection}>
        <div className={styles.sectionLabel}>Workspace</div>
        <nav className={styles.navList} aria-label="Developer workspace">
          {WORKSPACE_NAV.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `${styles.navItem} ${isActive ? styles.navItemActive : ''}`
                }
              >
                <Icon size={16} strokeWidth={1.65} aria-hidden="true" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>

      <div className={styles.navSection}>
        <div className={styles.sectionLabel}>Configuration</div>
        <nav className={styles.navList} aria-label="Configuration and documentation">
          <NavLink
            to="/app/settings"
            className={({ isActive }) =>
              `${styles.navItem} ${isActive ? styles.navItemActive : ''}`
            }
          >
            <Settings size={16} strokeWidth={1.65} aria-hidden="true" />
            <span>Settings</span>
          </NavLink>
          <a href="/docs" target="_blank" rel="noreferrer" className={styles.navItem}>
            <ExternalLink size={16} strokeWidth={1.65} aria-hidden="true" />
            <span>API Reference</span>
          </a>
        </nav>
      </div>

      <div className={styles.sidebarFooter}>
        <Link to="/app/settings" className={styles.accountLink}>
          <span className={styles.accountLabel}>
            {session?.authenticated ? 'Signed in as' : 'Customer session'}
          </span>
          <span className={styles.accountValue}>
            {session?.authenticated && session.email ? session.email : 'Sign in with email'}
          </span>
        </Link>
        <Link to="/" className={styles.publicBackLink}>
          Back to homepage
        </Link>
      </div>
    </div>
  );

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>{sidebarContent}</aside>

      {drawerOpen ? (
        <div
          className={styles.drawerBackdrop}
          role="dialog"
          aria-modal="true"
          aria-label="Workspace navigation"
          onClick={() => setDrawerOpen(false)}
        >
          <aside className={styles.drawerPanel} onClick={(e) => e.stopPropagation()}>
            {sidebarContent}
          </aside>
        </div>
      ) : null}

      <div className={styles.mainColumn}>
        <header className={styles.topBar}>
          <div className={styles.topBarLeft}>
            <button
              type="button"
              className={styles.menuBtn}
              onClick={() => setDrawerOpen(true)}
              aria-label="Open workspace navigation"
            >
              <Menu size={18} strokeWidth={1.75} />
            </button>
            <nav className={styles.breadcrumbs} aria-label="Breadcrumb">
              {breadcrumbs.map((crumb, idx) => (
                <span key={`${crumb.label}-${idx}`} className={styles.crumbItem}>
                  {idx > 0 ? <span className={styles.crumbSep}>/</span> : null}
                  {crumb.to ? (
                    <Link to={crumb.to} className={styles.crumbLink}>
                      {crumb.label}
                    </Link>
                  ) : (
                    <span className={styles.crumbCurrent}>{crumb.label}</span>
                  )}
                </span>
              ))}
            </nav>
          </div>

          <div className={styles.topBarRight}>
            {actions}
            <ThemeToggle />
          </div>
        </header>

        <main className={styles.content}>
          <div className={styles.pageHeader}>
            <h1 className={styles.pageTitle}>{title}</h1>
            {subtitle ? <p className={styles.pageSubtitle}>{subtitle}</p> : null}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
