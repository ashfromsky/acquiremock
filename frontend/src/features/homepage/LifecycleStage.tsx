import { useState } from 'react';
import { useHealth } from '../../hooks/useConsoleData';
import { formatAmount } from '../../utils/format';
import { handleTabListKeyDown } from '../../utils/tablist';
import styles from './LifecycleStage.module.css';

type StageKey = 'invoice' | 'checkout' | 'otp' | 'webhook';

interface StageTab {
  key: StageKey;
  index: string;
  label: string;
  endpoint: string;
}

const STAGES: StageTab[] = [
  { key: 'invoice', index: '01', label: 'Invoice API', endpoint: 'POST /api/create-invoice' },
  { key: 'checkout', index: '02', label: 'Hosted Checkout', endpoint: 'GET /checkout/{payment_id}' },
  { key: 'otp', index: '03', label: 'OTP Check', endpoint: 'POST /otp/verify/{payment_id}' },
  { key: 'webhook', index: '04', label: 'Signed Webhook', endpoint: 'X-Signature HMAC-SHA256' },
];

const STAGE_KEYS: readonly StageKey[] = STAGES.map((s) => s.key);

export function LifecycleStage() {
  const [activeStage, setActiveStage] = useState<StageKey>('checkout');
  const { data: health, isLoading, isError } = useHealth();

  const isHealthy = health?.status === 'ok';
  const currency = health?.currency || 'USD';
  const version = health?.version || '2.0.0';

  return (
    <div className={styles.stage} aria-label="Interactive payment lifecycle preview">
      <div className={styles.stageTop}>
        <div className={styles.tabs} role="tablist" aria-label="Payment lifecycle stages">
          {STAGES.map((stage) => {
            const active = activeStage === stage.key;
            return (
              <button
                key={stage.key}
                type="button"
                role="tab"
                tabIndex={active ? 0 : -1}
                aria-selected={active}
                className={`${styles.tab} ${active ? styles.tabActive : ''}`}
                onClick={() => setActiveStage(stage.key)}
                onKeyDown={(e) => handleTabListKeyDown(e, STAGE_KEYS, activeStage, setActiveStage)}
              >
                <span className={styles.tabIndex}>{stage.index}</span>
                <span>{stage.label}</span>
              </button>
            );
          })}
        </div>
        <span className={styles.endpointTag}>
          {STAGES.find((s) => s.key === activeStage)?.endpoint}
        </span>
      </div>

      <div className={styles.canvas} role="tabpanel">
        {activeStage === 'invoice' ? (
          <div className={styles.splitPreview}>
            <div className={styles.previewPane}>
              <div className={styles.paneLabel}>Request JSON</div>
              <pre className={styles.codeBlock}>{`{
  "amount": 25000,
  "reference": "ORDER-1042",
  "webhookUrl": "https://merchant.example/hook",
  "redirectUrl": "https://merchant.example/done"
}`}</pre>
            </div>
            <div className={styles.previewPane}>
              <div className={styles.paneLabel}>200 OK Response</div>
              <pre className={styles.codeBlock}>{`{
  "pageUrl": "http://localhost:8000/checkout/7b9c...41f2"
}`}</pre>
              <div className={styles.metaNote}>
                Expires automatically after 15 minutes if unpaid.
              </div>
            </div>
          </div>
        ) : null}

        {activeStage === 'checkout' ? (
          <div className={styles.splitPreview}>
            <div className={styles.cardArtifact}>
              <div className={styles.cardTop}>
                <img
                  src="/static/brand/mark-coral.png"
                  alt=""
                  width={26}
                  height={26}
                  className={styles.cardMark}
                />
                <span className={styles.cardScheme}>Sandbox Card</span>
              </div>
              <div className={styles.cardChip} aria-hidden="true" />
              <div className={styles.cardDigits}>4444  4444  4444  4444</div>
              <div className={styles.cardBottom}>
                <div>
                  <div className={styles.cardMetaLabel}>Valid thru</div>
                  <div className={styles.cardMetaVal}>12/30</div>
                </div>
                <div>
                  <div className={styles.cardMetaLabel}>CVV</div>
                  <div className={styles.cardMetaVal}>Any 3 digits</div>
                </div>
                <div>
                  <div className={styles.cardMetaLabel}>Outcome</div>
                  <div className={styles.cardMetaValCoral}>Approved</div>
                </div>
              </div>
            </div>

            <div className={styles.checkoutSummary}>
              <div className={styles.summaryRow}>
                <span>Order reference</span>
                <span className={styles.mono}>#ORDER-1042</span>
              </div>
              <div className={styles.summaryRow}>
                <span>Amount due</span>
                <span className={styles.mono}>
                  {formatAmount(25000, currency, currency === 'USD' ? '$' : currency)}
                </span>
              </div>
              <div className={styles.summaryRow}>
                <span>Form protection</span>
                <span className={styles.mono}>CSRF Strict cookie</span>
              </div>
              <div className={styles.summaryRow}>
                <span>Other card numbers</span>
                <span className={styles.mono}>402 INSUFFICIENT_FUNDS</span>
              </div>
            </div>
          </div>
        ) : null}

        {activeStage === 'otp' ? (
          <div className={styles.splitPreview}>
            <div className={styles.otpVisual}>
              <div className={styles.paneLabel}>4-Digit Confirmation</div>
              <div className={styles.otpDigits} aria-hidden="true">
                <span>4</span>
                <span>8</span>
                <span>2</span>
                <span>9</span>
              </div>
              <p className={styles.metaNote}>
                Sent via SMTP when configured, or logged directly to server stdout for local runs.
              </p>
            </div>
            <div className={styles.checkoutSummary}>
              <div className={styles.summaryRow}>
                <span>Endpoint</span>
                <span className={styles.mono}>POST /otp/verify/{'{id}'}</span>
              </div>
              <div className={styles.summaryRow}>
                <span>Resend rate limit</span>
                <span className={styles.mono}>3 requests / minute</span>
              </div>
              <div className={styles.summaryRow}>
                <span>Session cookie</span>
                <span className={styles.mono}>HMAC signed HttpOnly</span>
              </div>
              <div className={styles.summaryRow}>
                <span>Returning buyers</span>
                <span className={styles.mono}>Instant saved-card checkout</span>
              </div>
            </div>
          </div>
        ) : null}

        {activeStage === 'webhook' ? (
          <div className={styles.splitPreview}>
            <div className={styles.previewPane}>
              <div className={styles.paneLabel}>Sorted Compact Payload</div>
              <pre className={styles.codeBlock}>{`{"amount":25000,"card_mask":"**** 4444","payment_id":"7b9c...41f2","reference":"ORDER-1042","status":"paid","timestamp":"2026-11-27T12:14:00"}`}</pre>
            </div>
            <div className={styles.previewPane}>
              <div className={styles.paneLabel}>Delivery Headers</div>
              <pre className={styles.codeBlock}>{`Content-Type: application/json
X-Payment-ID: 7b9c...41f2
X-Signature: e4d1b7...90a3`}</pre>
              <div className={styles.metaNote}>
                Retries up to 5 times with exponential backoff on non-2xx responses.
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <div className={styles.stageBottom}>
        <div className={styles.healthStatus}>
          <span
            className={`${styles.statusDot} ${
              isLoading ? styles.dotMuted : isError ? styles.dotError : isHealthy ? styles.dotOk : styles.dotMuted
            }`}
            aria-hidden="true"
          />
          <span>
            {isLoading
              ? 'Checking gateway status'
              : isError
                ? 'Gateway status unavailable'
                : `Gateway v${version} active · ${currency}`}
          </span>
        </div>

        <a href="#lifecycle" className={styles.scrollCue}>
          Scroll to lifecycle
        </a>
      </div>
    </div>
  );
}
