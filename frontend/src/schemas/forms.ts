import { z } from 'zod';

const httpUrlSchema = z
  .string()
  .trim()
  .min(1, 'URL is required')
  .refine((val) => {
    try {
      const parsed = new URL(val);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch {
      return false;
    }
  }, 'Enter a valid http:// or https:// URL');

export const createInvoiceSchema = z.object({
  amount: z.coerce
    .number({ invalid_type_error: 'Enter an integer amount' })
    .int('Amount must be a whole integer in smallest units')
    .positive('Amount must be greater than 0'),
  reference: z
    .string()
    .trim()
    .min(1, 'Order reference is required')
    .max(120, 'Reference must be 120 characters or fewer'),
  webhookUrl: httpUrlSchema,
  redirectUrl: httpUrlSchema,
});

export type CreateInvoiceFormValues = z.infer<typeof createInvoiceSchema>;

export const adminLoginSchema = z.object({
  username: z.string().trim().min(1, 'Administrator username is required'),
  password: z.string().min(1, 'Administrator password is required'),
});

export type AdminLoginFormValues = z.infer<typeof adminLoginSchema>;

export const sendCodeSchema = z.object({
  email: z.string().trim().email('Enter a valid email address'),
});

export type SendCodeFormValues = z.infer<typeof sendCodeSchema>;

export const verifyCodeSchema = z.object({
  code: z
    .string()
    .trim()
    .regex(/^\d{4}$/, 'Enter the 4-digit verification code'),
});

export type VerifyCodeFormValues = z.infer<typeof verifyCodeSchema>;

export const webhookVerifySchema = z.object({
  payload: z.string().trim().min(2, 'JSON payload is required'),
  signature: z.string().trim().min(1, 'X-Signature header value is required'),
});

export type WebhookVerifyFormValues = z.infer<typeof webhookVerifySchema>;
