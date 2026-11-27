import { PublicLayout } from '../layouts/PublicLayout';
import { ButtonLink } from '../components/ui/Button';
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
            <ButtonLink to="/" variant="primary">
              Back to homepage
            </ButtonLink>
            <ButtonLink to="/app/overview" variant="secondary">
              Open workspace
            </ButtonLink>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
