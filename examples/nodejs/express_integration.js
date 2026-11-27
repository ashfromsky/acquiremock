const crypto = require("crypto");
const express = require("express");

const ACQUIREMOCK_BASE_URL = process.env.ACQUIREMOCK_BASE_URL || "http://localhost:8000";
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || "replace-with-matching-acquiremock-secret";
const MERCHANT_BASE_URL = process.env.MERCHANT_BASE_URL || "http://localhost:3001";
const PORT = Number(process.env.PORT || 3001);

const app = express();
app.use(express.json());

const ordersDb = new Map();

function sortKeysRecursively(value) {
  if (Array.isArray(value)) {
    return value.map(sortKeysRecursively);
  }
  if (value !== null && typeof value === "object") {
    return Object.keys(value)
      .sort()
      .reduce((acc, key) => {
        acc[key] = sortKeysRecursively(value[key]);
        return acc;
      }, {});
  }
  return value;
}

function verifyWebhookSignature(payload, signature, secret) {
  if (typeof signature !== "string" || !signature) {
    return false;
  }
  const canonical = JSON.stringify(sortKeysRecursively(payload));
  const expected = crypto
    .createHmac("sha256", secret)
    .update(canonical, "utf8")
    .digest("hex");

  const expectedBuf = Buffer.from(expected, "utf8");
  const actualBuf = Buffer.from(signature, "utf8");
  if (expectedBuf.length !== actualBuf.length) {
    return false;
  }
  return crypto.timingSafeEqual(expectedBuf, actualBuf);
}

app.post("/orders", async (req, res) => {
  const { orderId, amountMinor } = req.body;
  if (!orderId || !Number.isInteger(amountMinor) || amountMinor <= 0) {
    return res.status(400).json({ error: "orderId and positive integer amountMinor are required" });
  }

  try {
    const response = await fetch(`${ACQUIREMOCK_BASE_URL}/api/create-invoice`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        amount: amountMinor,
        reference: String(orderId),
        webhook_url: `${MERCHANT_BASE_URL}/webhooks/acquiremock`,
        redirect_url: `${MERCHANT_BASE_URL}/orders/${encodeURIComponent(orderId)}`,
      }),
    });

    if (!response.ok) {
      const detail = await response.text();
      return res.status(502).json({ error: "AcquireMock invoice creation failed", detail });
    }

    const data = await response.json();
    const order = {
      orderId: String(orderId),
      amountMinor,
      status: "pending",
      checkoutUrl: data.pageUrl,
      createdAt: new Date().toISOString(),
    };
    ordersDb.set(order.orderId, order);
    return res.status(201).json(order);
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
});

app.post("/webhooks/acquiremock", (req, res) => {
  const signature = req.header("X-Signature");
  const payload = req.body;

  if (!verifyWebhookSignature(payload, signature, WEBHOOK_SECRET)) {
    return res.status(401).json({ error: "Invalid webhook signature" });
  }

  if (payload.status === "paid" && payload.reference) {
    const order = ordersDb.get(payload.reference);
    if (order) {
      order.status = "paid";
      order.paymentId = payload.payment_id;
      order.paidAt = new Date().toISOString();
    }
  }

  return res.json({ received: true });
});

app.get("/orders/:orderId", (req, res) => {
  const order = ordersDb.get(req.params.orderId);
  if (!order) {
    return res.status(404).json({ error: "Order not found" });
  }
  return res.json(order);
});

app.listen(PORT, () => {
  console.log(`Merchant Express integration listening on port ${PORT}`);
});
