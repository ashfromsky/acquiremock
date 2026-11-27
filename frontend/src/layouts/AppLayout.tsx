import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity,
  CreditCard,
  ExternalLink,
  FlaskConical,
  LogOut,
  Menu,
  Settings,
  Webhook,
  X,
} from 'lucide-react';
import { BrandLogo } from '../components/BrandLogo';
import { ThemeToggle } from '../components/ThemeToggle';
import { useAdminLogout, useAdminSession } from '../hooks/useAdminAuth';
import { useToastStore } from '../store/toastStore';
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
  const navigate = useNavigate();
  const menuBtnRef = useRef<HTMLButtonElement>(null);
  const drawerCloseRef = useRef<HTMLButtonElement>(null);
  const { data: adminSession } = useAdminSession();
  const logoutMutation = useAdminLogout();
  const pushToast = useToastStore((s) => s.push);

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!drawerOpen) return;
    const prevFocus = document.activeElement as HTMLElement | null;
    drawerCloseRef.current?.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setDrawerOpen(false);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      prevFocus?.focus?.();
    };
  }, [drawerOpen]);

  async function handleAdminLogout() {
    try {
      await logoutMutation.mutateAsync();
      pushToast('Signed out of administrator console.', 'info');
      navigate('/app/login', { replace: true });
    } catch (err) {
      pushToast(err instanceof Error ? err.message : 'Sign out failed', 'error');
    }
  }

  function renderSidebarContent(isDrawer: boolean) {
    return (
      <div className={styles.sidebarInner}>
        <div className={styles.sidebarTop}>
          <Link to="/" className={styles.brandLink} aria-label="AcquireMock public homepage">
            <BrandLogo height={26} />
          </Link>
          <button
            ref={isDrawer ? drawerCloseRef : undefined}
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
          <div className={styles.adminSessionBox}>
            <div className={styles.adminIdentity}>
              <span className={styles.accountLabel}>Console admin</span>
              <span className={styles.accountValue}>
                {adminSession?.username || 'Administrator'}
              </span>
            </div>
            <button
              type="button"
              className={styles.logoutBtn}
              onClick={() => void handleAdminLogout()}
              disabled={logoutMutation.isPending}
              aria-label="Sign out of administrator console"
            >
              <LogOut size={14} strokeWidth={1.75} aria-hidden="true" />
              <span>Sign out</span>
            </button>
          </div>
          <Link to="/" className={styles.publicBackLink}>
            Back to homepage
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>{renderSidebarContent(false)}</aside>

      {drawerOpen ? (
        <div
          className={styles.drawerBackdrop}
          role="dialog"
          aria-modal="true"
          aria-label="Workspace navigation"
          onClick={() => setDrawerOpen(false)}
        >
          <aside className={styles.drawerPanel} onClick={(e) => e.stopPropagation()}>
            {renderSidebarContent(true)}
          </aside>
        </div>
      ) : null}

      <div className={styles.mainColumn}>
        <header className={styles.topBar}>
          <div className={styles.topBarLeft}>
            <button
              ref={menuBtnRef}
              type="button"
              className={styles.menuBtn}
              onClick={() => setDrawerOpen(true)}
              aria-expanded={drawerOpen}
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
