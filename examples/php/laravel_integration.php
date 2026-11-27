<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class AcquireMockController extends Controller
{
    private function baseUrl(): string
    {
        return rtrim((string) config('services.acquiremock.base_url', 'http://localhost:8000'), '/');
    }

    private function webhookSecret(): string
    {
        return (string) config('services.acquiremock.webhook_secret', '');
    }

    private function sortKeysRecursively(mixed $value): mixed
    {
        if (!is_array($value)) {
            return $value;
        }
        if (!array_is_list($value)) {
            ksort($value, SORT_STRING);
        }
        foreach ($value as $k => $v) {
            $value[$k] = $this->sortKeysRecursively($v);
        }
        return $value;
    }

    public function verifyWebhookSignature(array $payload, string $signature, string $secret): bool
    {
        $sorted = $this->sortKeysRecursively($payload);
        $canonical = json_encode($sorted, JSON_UNESCAPED_SLASHES);
        if ($canonical === false || $signature === '' || $secret === '') {
            return false;
        }

        $expected = hash_hmac('sha256', $canonical, $secret);
        return hash_equals($expected, $signature);
    }

    public function createOrder(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'order_id' => ['required', 'string', 'max:64'],
            'amount_minor' => ['required', 'integer', 'min:1'],
        ]);

        $response = Http::timeout(10)->post($this->baseUrl() . '/api/create-invoice', [
            'amount' => $validated['amount_minor'],
            'reference' => $validated['order_id'],
            'webhook_url' => url('/api/webhooks/acquiremock'),
            'redirect_url' => url('/orders/' . urlencode($validated['order_id'])),
        ]);

        if (!$response->successful()) {
            return response()->json([
                'error' => 'Failed to create AcquireMock invoice',
                'detail' => $response->body(),
            ], 502);
        }

        return response()->json([
            'order_id' => $validated['order_id'],
            'amount_minor' => $validated['amount_minor'],
            'checkout_url' => $response->json('pageUrl'),
        ], 201);
    }

    public function handleWebhook(Request $request): JsonResponse
    {
        $signature = (string) $request->header('X-Signature', '');
        $payload = $request->json()->all();

        if (!$this->verifyWebhookSignature($payload, $signature, $this->webhookSecret())) {
            Log::warning('AcquireMock webhook signature mismatch', [
                'payment_id' => $payload['payment_id'] ?? null,
            ]);
            return response()->json(['error' => 'Invalid webhook signature'], 401);
        }

        if (($payload['status'] ?? null) === 'paid') {
            Log::info('AcquireMock payment settled', [
                'payment_id' => $payload['payment_id'] ?? null,
                'reference' => $payload['reference'] ?? null,
                'amount_minor' => $payload['amount'] ?? null,
            ]);
        }

        return response()->json(['received' => true]);
    }
}
