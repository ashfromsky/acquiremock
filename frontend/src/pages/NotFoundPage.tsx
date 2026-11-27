import { Link } from 'react-router-dom';
import { PublicLayout } from '../layouts/PublicLayout';
import { Button } from '../components/ui/Button';
import styles from './NotFoundPage.module.css';

export function NotFoundPage() {
  return (
    <PublicLayout>
      <section className={styles.wrap}>
        <div className={styles.card}>
          <span className={`${styles.code} mono-num`}>404</span>
          <h1 className={styles.title}>Page not found</h1>
          <p className={styles.copy}>
            The route you requested does not exist in AcquireMock. Return to the homepage or open the developer workspace.
          </p>
          <div className={styles.actions}>
            <Link to="/">
              <Button variant="primary">Back to homepage</Button>
            </Link>
            <Link to="/app/overview">
              <Button variant="secondary">Open workspace</Button>
            </Link>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
