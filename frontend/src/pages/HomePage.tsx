import { useState } from 'react';
import { Link } from 'react-router-dom';
import { PublicLayout } from '../layouts/PublicLayout';
import { ButtonLink } from '../components/ui/Button';
import { CopyButton } from '../components/ui/CopyButton';
import { LifecycleStage } from '../features/homepage/LifecycleStage';
import { getRuntimeBaseUrl } from '../utils/format';
import { handleTabListKeyDown } from '../utils/tablist';
import styles from './HomePage.module.css';

type CodeLang = 'curl' | 'python' | 'node';
const CODE_LANGS: readonly CodeLang[] = ['curl', 'python', 'node'];

const LIFECYCLE_STEPS = [
  {
    index: '01',
    title: 'Create invoice',
    endpoint: 'POST /api/create-invoice',
    body: 'Send an integer amount, order reference, webhook URL, and redirect URL. AcquireMock validates target URLs against SSRF, sets a 15-minute expiry window, and returns a hosted checkout URL.',
  },
  {
    index: '02',
    title: 'Hosted checkout and saved cards',
    endpoint: 'GET /checkout/{payment_id}',
    body: 'Customers pay on a server-rendered checkout protected by a double-submit CSRF cookie. Card 4444 4444 4444 4444 succeeds; any other card triggers a 402 insufficient funds failure.',
  },
  {
    index: '03',
    title: 'Email OTP verification',
    endpoint: 'POST /otp/verify/{payment_id}',
    body: 'First-time payers confirm with a 4-digit OTP delivered via SMTP or printed to stdout in local development. Verification issues a signed HttpOnly session cookie for subsequent saved-card payments.',
  },
  {
    index: '04',
    title: 'Signed webhook delivery',
    endpoint: 'POST {webhookUrl}',
    body: 'AcquireMock dispatches compact sorted JSON signed with HMAC-SHA256 in the X-Signature header, records each attempt in webhook_logs, and retries failed deliveries with persisted exponential backoff up to 5 times.',
  },
];

const SECURITY_SPECS = [
  {
    label: 'HMAC-SHA256 webhook signatures',
    detail: 'Serialized with sorted keys and compact separators, verified in constant time via POST /webhooks/verify.',
  },
  {
    label: 'Isolated admin and customer sessions',
    detail: 'Developer console APIs enforce administrator login and CSRF tokens separately from customer saved-card cookies.',
  },
  {
    label: 'Double-submit CSRF protection',
    detail: 'Checkout, OTP, and console actions verify CSRF tokens in constant time with hmac.compare_digest.',
  },
  {
    label: 'DNS-pinned SSRF protection',
    detail: 'Webhook targets resolve and validate all A/AAAA records and pin connections to prevent private IP and DNS rebinding attacks.',
  },
  {
    label: 'Scoped Idempotency-Key deduplication',
    detail: 'Retrying POST /api/pay/{payment_id} with the same key and payload replays the outcome while rejecting cross-payment or mismatched reuse.',
  },
  {
    label: 'Per-IP and OTP lockout controls',
    detail: 'SlowAPI rate limits and database-backed 5-attempt OTP lockouts protect payment verification and customer authentication.',
  },
];

function getCodeSnippet(lang: CodeLang, baseUrl: string): string {
  if (lang === 'curl') {
    return `curl -X POST ${baseUrl}/api/create-invoice \\
  -H "Content-Type: application/json" \\
  -d '{
    "amount": 25000,
    "reference": "ORDER-1042",
    "webhookUrl": "https://your-site.com/webhook",
    "redirectUrl": "https://your-site.com/success"
  }'`;
  }

  if (lang === 'python') {
    return `import hashlib
import hmac
import json

def verify_acquiremock_signature(payload: dict, signature: str, secret: str) -> bool:
    message = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)`;
  }

  return `import crypto from "node:crypto";

function sortKeys(value) {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === "object") {
    return Object.keys(value).sort().reduce((acc, key) => {
      acc[key] = sortKeys(value[key]);
      return acc;
    }, {});
  }
  return value;
}

export function verifyAcquireMockSignature(payload, signature, secret) {
  const message = JSON.stringify(sortKeys(payload));
  const expected = crypto.createHmac("sha256", secret).update(message).digest("hex");
  const sigBuf = Buffer.from(signature);
  const expBuf = Buffer.from(expected);
  return sigBuf.length === expBuf.length && crypto.timingSafeEqual(sigBuf, expBuf);
}`;
}

export function HomePage() {
  const [codeLang, setCodeLang] = useState<CodeLang>('curl');
  const baseUrl = getRuntimeBaseUrl();
  const snippet = getCodeSnippet(codeLang, baseUrl);

  return (
    <PublicLayout>
      <section className={styles.heroSection}>
        <div className={styles.heroGrid}>
          <div className={styles.heroSpacer} aria-hidden="true" />
          <h1 className={styles.heroTitle}>
            AcquireMock is a mock payment gateway built for testing integrations end to end
          </h1>

          <p className={styles.heroCaption}>
            Test full payment lifecycles.
            <br />
            From invoice API to signed webhook.
          </p>

          <div className={styles.heroBody}>
            <p className={styles.heroCopy}>
              Simulate hosted card checkout, email OTP verification, saved cards, and HMAC-SHA256 webhooks on your local machine or staging environment without external PSP credentials or real money.
            </p>
            <div className={styles.heroActions}>
              <ButtonLink to="/app/testing" variant="primary">
                Open payment playground
              </ButtonLink>
              <ButtonLink to="/app/overview" variant="secondary">
                Open developer console
              </ButtonLink>
            </div>
          </div>
        </div>

        <div className={styles.stageContainer}>
          <LifecycleStage />
        </div>
      </section>

      <section id="lifecycle" className={styles.lifecycleSection}>
        <div className={styles.lifecycleGrid}>
          <div className={styles.lifecycleIntro}>
            <h2 className={styles.sectionHeading}>
              Four real stages, zero external dependencies
            </h2>
            <p className={styles.sectionLead}>
              Built with FastAPI, SQLModel, and server-rendered checkout flows so your application tests the exact HTTP redirects, cookies, and callbacks a production gateway sends.
            </p>
            <div className={styles.introAction}>
              <Link to="/app/payments" className={styles.inlineLink}>
                Inspect live payment records
              </Link>
            </div>
          </div>

          <div className={styles.lifecycleList}>
            {LIFECYCLE_STEPS.map((step) => (
              <article key={step.index} className={styles.lifecycleRow}>
                <div className={styles.rowHeader}>
                  <span className={styles.rowIndex}>{step.index}</span>
                  <h3 className={styles.rowTitle}>{step.title}</h3>
                  <span className={styles.rowEndpoint}>{step.endpoint}</span>
                </div>
                <p className={styles.rowBody}>{step.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.contrastSection}>
        <div className={styles.contrastInner}>
          <div className={styles.contrastHeader}>
            <div>
              <h2 className={styles.contrastHeading}>
                Drop into your backend in one POST request
              </h2>
              <p className={styles.contrastLead}>
                Create an invoice from cURL or your backend service, then verify every incoming webhook using your shared WEBHOOK_SECRET.
              </p>
            </div>
            <ButtonLink to="/app/testing" variant="coral">
              Test payload in playground
            </ButtonLink>
          </div>

          <div className={styles.contrastGrid}>
            <div className={styles.codePanel}>
              <div className={styles.codeBar}>
                <div className={styles.langTabs} role="tablist" aria-label="Integration language examples">
                  {CODE_LANGS.map((lang) => (
                    <button
                      key={lang}
                      type="button"
                      role="tab"
                      tabIndex={codeLang === lang ? 0 : -1}
                      aria-selected={codeLang === lang}
                      className={`${styles.langTab} ${codeLang === lang ? styles.langTabActive : ''}`}
                      onClick={() => setCodeLang(lang)}
                      onKeyDown={(e) => handleTabListKeyDown(e, CODE_LANGS, codeLang, setCodeLang)}
                    >
                      {lang === 'curl' ? 'cURL' : lang === 'python' ? 'Python' : 'Node.js'}
                    </button>
                  ))}
                </div>
                <CopyButton value={snippet} compact />
              </div>
              <pre className={styles.codeContent}>{snippet}</pre>
            </div>

            <aside className={styles.cardSpecPanel} aria-label="Sandbox test card reference">
              <h3 className={styles.specTitle}>Sandbox test card rules</h3>
              <dl className={styles.specList}>
                <div className={styles.specRow}>
                  <dt>Approved card</dt>
                  <dd className={styles.specMono}>4444 4444 4444 4444</dd>
                </div>
                <div className={styles.specRow}>
                  <dt>Expiry and CVV</dt>
                  <dd>Any future MM/YY and any 3 digits</dd>
                </div>
                <div className={styles.specRow}>
                  <dt>Declined card</dt>
                  <dd>Any other number returns 402 INSUFFICIENT_FUNDS</dd>
                </div>
                <div className={styles.specRow}>
                  <dt>Invoice expiry</dt>
                  <dd>15 minutes from creation</dd>
                </div>
              </dl>
            </aside>
          </div>
        </div>
      </section>

      <section className={styles.securitySection}>
        <div className={styles.securityInner}>
          <div className={styles.securityHeader}>
            <h2 className={styles.sectionHeading}>
              Production security patterns built into the sandbox
            </h2>
            <p className={styles.sectionLead}>
              Every safeguard listed below is enforced in the running FastAPI backend.
            </p>
          </div>

          <div className={styles.securityGrid}>
            {SECURITY_SPECS.map((item) => (
              <div key={item.label} className={styles.securityItem}>
                <h3 className={styles.securityTitle}>{item.label}</h3>
                <p className={styles.securityDetail}>{item.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
