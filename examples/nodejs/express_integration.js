/**
 * AcquireMock Integration Example - Express.js
 * =============================================
 *
 * This example shows how to integrate AcquireMock with Express.js
 *
 * Installation:
 *   npm install express axios body-parser crypto
 *
 * Run:
 *   node express_integration.js
 */

const express = require('express');
const axios = require('axios');
const crypto = require('crypto');
const bodyParser = require('body-parser');

// Configuration
const ACQUIREMOCK_URL = process.env.ACQUIREMOCK_URL || 'http://localhost:8000';
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || 'your_webhook_secret_here';
const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const PORT = process.env.PORT || 3000;

const app = express();
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// Mock database
const orders = new Map();

/**
 * Calculate order amount in cents
 */
function calculateOrderAmount(productId, quantity) {
  const prices = {
    'product_1': 2500,  // $25.00
    'product_2': 5000,  // $50.00
    'product_3': 10000  // $100.00
  };
  return (prices[productId] || 0) * quantity;
}

/**
 * Verify webhook signature using HMAC-SHA256
 */
function verifyWebhookSignature(payload, signature) {
  const message = JSON.stringify(payload, Object.keys(payload).sort());
  const expectedSignature = crypto
    .createHmac('sha256', WEBHOOK_SECRET)
    .update(message)
    .digest('hex');

  const sigBuf = Buffer.from(signature);
  const expBuf = Buffer.from(expectedSignature);
  if (sigBuf.length !== expBuf.length) {
    return false;
  }

  return crypto.timingSafeEqual(sigBuf, expBuf);
}

/**
 * Create payment invoice via AcquireMock API
 */
async function createPaymentInvoice(orderId, amount) {
  const payload = {
    amount: amount,
    reference: orderId,
    webhookUrl: `${BASE_URL}/webhook/payment`,
    redirectUrl: `${BASE_URL}/order/${orderId}/success`
  };

  try {
    const response = await axios.post(
      `${ACQUIREMOCK_URL}/api/create-invoice`,
      payload,
      { timeout: 10000 }
    );
    return response.data.pageUrl;
  } catch (error) {
    throw new Error(`Payment gateway error: ${error.message}`);
  }
}

/**
 * Routes
 */

// Home page
app.get('/', (req, res) => {
  res.json({
    service: 'E-Commerce Store (Node.js)',
    payment_gateway: 'AcquireMock',
    endpoints: {
      create_order: 'POST /orders',
      get_order: 'GET /orders/:orderId',
      webhook: 'POST /webhook/payment'
    }
  });
});

// Create order
app.post('/orders', async (req, res) => {
  const { product_id, quantity, customer_email } = req.body;

  if (!product_id || !quantity || !customer_email) {
    return res.status(400).json({
      error: 'Missing required fields: product_id, quantity, customer_email'
    });
  }

  // Generate order ID
  const orderId = `ORDER-${Date.now()}`;

  // Calculate amount
  const amount = calculateOrderAmount(product_id, quantity);
  if (amount === 0) {
    return res.status(404).json({ error: 'Product not found' });
  }

  try {
    // Create payment invoice
    const paymentUrl = await createPaymentInvoice(orderId, amount);

    // Save order
    const order = {
      id: orderId,
      product_id,
      quantity,
      amount,
      status: 'pending',
      customer_email,
      payment_url: paymentUrl,
      created_at: new Date().toISOString()
    };

    orders.set(orderId, order);

    res.status(201).json(order);
  } catch (error) {
    res.status(503).json({ error: error.message });
  }
});

// Get order
app.get('/orders/:orderId', (req, res) => {
  const order = orders.get(req.params.orderId);

  if (!order) {
    return res.status(404).json({ error: 'Order not found' });
  }

  res.json(order);
});

// Webhook handler
app.post('/webhook/payment', (req, res) => {
  const signature = req.headers['x-signature'];
  const payload = req.body;

  // Verify signature
  if (!signature) {
    return res.status(403).json({ error: 'Missing signature' });
  }

  try {
    if (!verifyWebhookSignature(payload, signature)) {
      return res.status(403).json({ error: 'Invalid signature' });
    }
  } catch (error) {
    return res.status(403).json({ error: 'Signature verification failed' });
  }

  // Get order
  const order = orders.get(payload.reference);
  if (!order) {
    console.log(`Order ${payload.reference} not found`);
    return res.json({ status: 'ok' }); // Return 200 to prevent retries
  }

  // Update order status
  if (payload.status === 'paid') {
    order.status = 'paid';
    console.log(`✅ Order ${order.id} marked as PAID`);

    // Here you would:
    // - Send confirmation email
    // - Trigger fulfillment
    // - Update inventory

  } else if (payload.status === 'failed') {
    order.status = 'failed';
    console.log(`❌ Order ${order.id} payment FAILED`);

  } else if (payload.status === 'expired') {
    order.status = 'expired';
    console.log(`⏰ Order ${order.id} payment EXPIRED`);
  }

  orders.set(order.id, order);

  res.json({
    status: 'ok',
    order_id: order.id,
    processed_at: new Date().toISOString()
  });
});

// Success page
app.get('/order/:orderId/success', (req, res) => {
  const order = orders.get(req.params.orderId);

  if (!order) {
    return res.status(404).json({ error: 'Order not found' });
  }

  res.json({
    message: 'Payment successful!',
    order_id: order.id,
    amount: order.amount,
    status: order.status
  });
});

// Health check
app.get('/health', async (req, res) => {
  let gatewayHealthy = false;

  try {
    const response = await axios.get(`${ACQUIREMOCK_URL}/health`, { timeout: 5000 });
    gatewayHealthy = response.status === 200;
  } catch (error) {
    gatewayHealthy = false;
  }

  res.json({
    status: 'healthy',
    payment_gateway: gatewayHealthy ? 'healthy' : 'unhealthy',
    timestamp: new Date().toISOString()
  });
});

// Start server
app.listen(PORT, () => {
  console.log('🚀 Starting E-Commerce API...');
  console.log(`📦 Orders endpoint: http://localhost:${PORT}/orders`);
  console.log(`🔔 Webhook endpoint: http://localhost:${PORT}/webhook/payment`);
  console.log(`💳 Payment Gateway: ${ACQUIREMOCK_URL}`);
  console.log('');
  console.log('Test it:');
  console.log(`curl -X POST http://localhost:${PORT}/orders \\`);
  console.log(`  -H "Content-Type: application/json" \\`);
  console.log(`  -d '{"product_id":"product_1","quantity":2,"customer_email":"test@example.com"}'`);
});

module.exports = app;