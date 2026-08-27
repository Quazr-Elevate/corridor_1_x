import { z } from "zod";

export const gstinRegex = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
export const panRegex = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/;
export const pincodeRegex = /^[1-9][0-9]{5}$/;
export const phoneRegex = /^[6-9][0-9]{9}$/;
// Person name: must start with a letter, then letters/spaces/. ' - only.
// Blocks digits and other special characters. Allows names like "O'Brien",
// "Smith-Jones", "J. Sharma".
export const personNameRegex = /^[A-Za-z][A-Za-z\s.'-]{1,99}$/;

export const gstinField = z
  .string()
  .trim()
  .toUpperCase()
  .regex(gstinRegex, "Enter a valid 15-character GSTIN");

export const panField = z
  .string()
  .trim()
  .toUpperCase()
  .regex(panRegex, "Enter a valid 10-character PAN");

export const pincodeField = z.string().trim().regex(pincodeRegex, "Enter a valid 6-digit pincode");

export const phoneField = z
  .string()
  .trim()
  .regex(phoneRegex, "Enter a valid 10-digit Indian mobile number");

export const emailField = z.string().trim().toLowerCase().email("Enter a valid email");

export const personNameField = z
  .string()
  .trim()
  .min(2, "Enter at least 2 characters")
  .max(100, "Name is too long")
  .regex(personNameRegex, "Name should not contain numbers");

export const sellerGstinSchema = z.object({
  gstin: gstinField,
  companyName: z.string().min(2, "Required"),
  pan: panField,
  businessType: z.string().min(1, "Required"),
  natureOfBusiness: z.string().optional(),
  ownerName: personNameField,
  building: z.string().optional(),
  pincode: pincodeField,
  city: z.string().min(1, "Required"),
  state: z.string().min(1, "Required"),
  district: z.string().optional(),
  country: z.string().default("India"),
  mobile: phoneField,
  email: emailField.optional().or(z.literal("")),
});

export const sellerPanSchema = z.object({
  pan: panField,
  ownerName: personNameField,
  companyName: z.string().min(2, "Required"),
  building: z.string().optional(),
  pincode: pincodeField,
  city: z.string().min(1, "Required"),
  state: z.string().min(1, "Required"),
  country: z.string().default("India"),
  mobile: phoneField,
  email: emailField.optional().or(z.literal("")),
});

export type SellerGstinValues = z.infer<typeof sellerGstinSchema>;
export type SellerPanValues = z.infer<typeof sellerPanSchema>;

export const buyerSchema = z.object({
  fullName: personNameField,
  companyName: z.string().min(2, "Enter your company name"),
  country: z.string().min(1, "Select a country"),
  city: z.string().optional().or(z.literal("")),
  mobile: phoneField,
  email: emailField.optional().or(z.literal("")),
});

export type BuyerValues = z.infer<typeof buyerSchema>;
