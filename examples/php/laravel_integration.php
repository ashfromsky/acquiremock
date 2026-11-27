<?php

/**
 * AcquireMock Integration Example - Laravel
 * ==========================================
 *
 * This example shows how to integrate AcquireMock with Laravel
 *
 * Installation:
 *   composer require guzzlehttp/guzzle
 *
 * Usage:
 *   Add this controller to your Laravel app:
 *   app/Http/Controllers/PaymentController.php
 */

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\DB;
use GuzzleHttp\Client;

class PaymentController extends Controller
{
    private $acquiremockUrl;
    private $webhookSecret;
    private $baseUrl;

    public function __construct()
    {
        $this->acquiremockUrl = env('ACQUIREMOCK_URL', 'http://localhost:8000');
        $this->webhookSecret = env('WEBHOOK_SECRET', 'your_webhook_secret_here');
        $this->baseUrl = env('APP_URL', 'http://localhost:8080');
    }

    /**
     * Create a new order and payment
     *
     * POST /api/orders
     * {
     *   "product_id": "product_1",
     *   "quantity": 2,
     *   "customer_email": "customer@example.com"
     * }
     */
    public function createOrder(Request $request)
    {
        $validated = $request->validate([
            'product_id' => 'required|string',
            'quantity' => 'required|integer|min:1',
            'customer_email' => 'required|email'
        ]);

        // Generate order ID
        $orderId = 'ORDER-' . time();

        // Calculate amount
        $amount = $this->calculateOrderAmount(
            $validated['product_id'],
            $validated['quantity']
        );

        if ($amount === 0) {
            return response()->json(['error' => 'Product not found'], 404);
        }

        try {
            // Create payment invoice
            $paymentUrl = $this->createPaymentInvoice($orderId, $amount);

            // Save order to database
            DB::table('orders')->insert([
                'id' => $orderId,
                'product_id' => $validated['product_id'],
                'quantity' => $validated['quantity'],
                'amount' => $amount,
                'status' => 'pending',
                'customer_email' => $validated['customer_email'],
                'payment_url' => $paymentUrl,
                'created_at' => now(),
                'updated_at' => now()
            ]);

            return response()->json([
                'order_id' => $orderId,
                'amount' => $amount,
                'status' => 'pending',
                'payment_url' => $paymentUrl
            ], 201);

        } catch (\Exception $e) {
            Log::error('Payment creation failed: ' . $e->getMessage());
            return response()->json([
                'error' => 'Payment gateway error'
            ], 503);
        }
    }

    /**
     * Get order details
     *
     * GET /api/orders/{orderId}
     */
    public function getOrder($orderId)
    {
        $order = DB::table('orders')->where('id', $orderId)->first();

        if (!$order) {
            return response()->json(['error' => 'Order not found'], 404);
        }

        return response()->json($order);
    }

    /**
     * Handle payment webhook from AcquireMock
     *
     * POST /webhook/payment
     */
    public function paymentWebhook(Request $request)
    {
        // Get signature from header
        $signature = $request->header('X-Signature');

        if (!$signature) {
            return response()->json(['error' => 'Missing signature'], 403);
        }

        // Get payload
        $payload = $request->all();

        // Verify signature
        if (!$this->verifyWebhookSignature($payload, $signature)) {
            Log::warning('Invalid webhook signature', ['payload' => $payload]);
            return response()->json(['error' => 'Invalid signature'], 403);
        }

        // Find order
        $order = DB::table('orders')
            ->where('id', $payload['reference'])
            ->first();

        if (!$order) {
            Log::error('Order not found', ['reference' => $payload['reference']]);
            return response()->json(['status' => 'ok']); // Return 200 to prevent retries
        }

        // Update order status
        $newStatus = $payload['status'];

        DB::table('orders')
            ->where('id', $order->id)
            ->update([
                'status' => $newStatus,
                'updated_at' => now()
            ]);

        // Log the event
        if ($newStatus === 'paid') {
            Log::info("✅ Order {$order->id} marked as PAID");

            // Send confirmation email
            // Mail::to($order->customer_email)->send(new OrderConfirmation($order));

            // Trigger fulfillment
            // event(new OrderPaid($order));

        } elseif ($newStatus === 'failed') {
            Log::warning("❌ Order {$order->id} payment FAILED");

        } elseif ($newStatus === 'expired') {
            Log::info("⏰ Order {$order->id} payment EXPIRED");
        }

        return response()->json([
            'status' => 'ok',
            'order_id' => $order->id,
            'processed_at' => now()->toIso8601String()
        ]);
    }

    /**
     * Success page after payment
     *
     * GET /order/{orderId}/success
     */
    public function orderSuccess($orderId)
    {
        $order = DB::table('orders')->where('id', $orderId)->first();

        if (!$order) {
            return response()->json(['error' => 'Order not found'], 404);
        }

        return response()->json([
            'message' => 'Payment successful!',
            'order_id' => $order->id,
            'amount' => $order->amount,
            'status' => $order->status
        ]);
    }

    /**
     * Calculate order amount in cents
     */
    private function calculateOrderAmount($productId, $quantity)
    {
        $prices = [
            'product_1' => 2500,  // $25.00
            'product_2' => 5000,  // $50.00
            'product_3' => 10000, // $100.00
        ];

        return ($prices[$productId] ?? 0) * $quantity;
    }

    /**
     * Create payment invoice via AcquireMock API
     */
    private function createPaymentInvoice($orderId, $amount)
    {
        $client = new Client();

        $response = $client->post("{$this->acquiremockUrl}/api/create-invoice", [
            'json' => [
                'amount' => $amount,
                'reference' => $orderId,
                'webhookUrl' => "{$this->baseUrl}/webhook/payment",
                'redirectUrl' => "{$this->baseUrl}/order/{$orderId}/success"
            ],
            'timeout' => 10
        ]);

        $data = json_decode($response->getBody(), true);
        return $data['pageUrl'];
    }

    /**
     * Verify webhook signature using HMAC-SHA256
     */
    private function verifyWebhookSignature($payload, $signature)
    {
        // Sort payload keys
        ksort($payload);

        // Create message
        $message = json_encode($payload, JSON_UNESCAPED_SLASHES);

        // Calculate expected signature
        $expectedSignature = hash_hmac('sha256', $message, $this->webhookSecret);

        // Constant-time comparison
        return hash_equals($expectedSignature, $signature);
    }
}

/**
 * Routes (add to routes/api.php):
 *
 * use App\Http\Controllers\PaymentController;
 *
 * Route::post('/orders', [PaymentController::class, 'createOrder']);
 * Route::get('/orders/{orderId}', [PaymentController::class, 'getOrder']);
 * Route::post('/webhook/payment', [PaymentController::class, 'paymentWebhook']);
 * Route::get('/order/{orderId}/success', [PaymentController::class, 'orderSuccess']);
 */

/**
 * Database Migration:
 *
 * php artisan make:migration create_orders_table
 *
 * public function up()
 * {
 *     Schema::create('orders', function (Blueprint $table) {
 *         $table->string('id')->primary();
 *         $table->string('product_id');
 *         $table->integer('quantity');
 *         $table->integer('amount');
 *         $table->string('status');
 *         $table->string('customer_email');
 *         $table->string('payment_url')->nullable();
 *         $table->timestamps();
 *     });
 * }
 */

/**
 * Environment Variables (.env):
 *
 * ACQUIREMOCK_URL=http://localhost:8000
 * WEBHOOK_SECRET=your_webhook_secret_here
 * APP_URL=http://localhost:8080
 */

/**
 * Testing:
 *
 * curl -X POST http://localhost:8080/api/orders \
 *   -H "Content-Type: application/json" \
 *   -d '{
 *     "product_id": "product_1",
 *     "quantity": 2,
 *     "customer_email": "test@example.com"
 *   }'
 */