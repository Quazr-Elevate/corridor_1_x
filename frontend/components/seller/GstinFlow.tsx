"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Building2, MapPin, Phone } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { FieldWithAction } from "@/components/ui/FieldWithAction";
import { OtpModal } from "@/components/ui/OtpModal";
import { SectionHead } from "@/components/ui/SectionHead";
import { TextField } from "@/components/ui/TextField";
import { api, type GstinLookup } from "@/lib/api";
import {
  gstinRegex,
  phoneRegex,
  sellerGstinSchema,
  type SellerGstinValues,
} from "@/lib/validation";

interface Props {
  onComplete: (payload: SellerGstinValues) => void;
}

export function GstinFlow({ onComplete }: Props) {
  // GSTIN lookup
  const [gstinInput, setGstinInput] = useState("");
  const [gstinError, setGstinError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(false);
  const [gstinFetched, setGstinFetched] = useState(false);

  // Mobile OTP (Day-1: user enters their own mobile, not derived from GSTIN)
  const [mobileInput, setMobileInput] = useState("");
  const [mobileError, setMobileError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [verified, setVerified] = useState(false);
  const [otp, setOtp] = useState<{
    open: boolean;
    otpId?: string;
    destination?: string;
    devHint?: string;
  }>({ open: false });

  const [submitError, setSubmitError] = useState<string | null>(null);

  const gstinValid = gstinRegex.test(gstinInput.trim().toUpperCase());
  const mobileValid = phoneRegex.test(mobileInput.trim());

  const form = useForm<SellerGstinValues>({
    resolver: zodResolver(sellerGstinSchema),
    mode: "onBlur",
    defaultValues: {
      gstin: "",
      companyName: "",
      pan: "",
      businessType: "",
      natureOfBusiness: "",
      ownerName: "",
      building: "",
      pincode: "",
      city: "",
      state: "",
      district: "",
      country: "India",
      mobile: "",
      email: "",
    },
  });

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = form;

  const applyGstin = (data: GstinLookup) => {
    setValue("gstin", data.gstin);
    setValue("companyName", data.legalName);
    setValue("pan", data.pan);
    setValue("businessType", data.businessType);
    setValue("natureOfBusiness", data.natureOfBusiness ?? "");
    setValue("city", data.address.city);
    setValue("state", data.address.state);
    setValue("district", data.address.district ?? "");
    setValue("pincode", data.address.pincode);
    // Building address is intentionally NOT auto-filled — user provides their
    // actual operating address (may differ from GST registered address).
  };

  const handleVerifyGstin = async () => {
    setGstinError(null);
    const gstin = gstinInput.trim().toUpperCase();
    if (!gstinRegex.test(gstin)) {
      setGstinError("Enter a valid 15-character GSTIN");
      return;
    }
    setFetching(true);
    try {
      const data = await api.lookupGstin(gstin);
      applyGstin(data);
      setGstinFetched(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not verify GSTIN";
      setGstinError(msg);
    } finally {
      setFetching(false);
    }
  };

  const handleSendOtp = async () => {
    setMobileError(null);
    if (!phoneRegex.test(mobileInput.trim())) {
      setMobileError("Enter a valid 10-digit mobile number");
      return;
    }
    setSending(true);
    try {
      const res = await api.sendOtp({
        channel: "phone",
        value: mobileInput.trim(),
        purpose: "phone",
      });
      setValue("mobile", mobileInput.trim());
      setOtp({
        open: true,
        otpId: res.otpId,
        destination: res.destination,
        devHint: res.devHint,
      });
    } catch (err) {
      setMobileError(err instanceof Error ? err.message : "Could not send code");
    } finally {
      setSending(false);
    }
  };

  const handleVerify = async (code: string) => {
    if (!otp.otpId) return { ok: false, error: "Session expired" };
    try {
      const res = await api.verifyOtp({
        otpId: otp.otpId,
        code,
        mobile: mobileInput.trim(),
      });
      if (res.ok) {
        setVerified(true);
        setOtp({ open: false });
      }
      return res;
    } catch (err) {
      return {
        ok: false,
        error: err instanceof Error ? err.message : "Verification failed",
      };
    }
  };

  const handleResend = async () => {
    if (!mobileInput) return;
    await api.sendOtp({ channel: "phone", value: mobileInput.trim(), purpose: "phone" });
  };

  const onValid = async (values: SellerGstinValues) => {
    setSubmitError(null);
    try {
      await api.submitSeller({ ...values, onboardingPath: "gstin" });
      onComplete(values);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong";
      setSubmitError(msg);
      // If backend rejected because the GSTIN is already on file, unlock the
      // GSTIN input so the user can enter a different one and re-verify.
      if (/already|duplicate|registered|exists/i.test(msg)) {
        setGstinFetched(false);
      }
    }
  };

  return (
    <form onSubmit={handleSubmit(onValid)} className="space-y-6" noValidate>
      {/* Step 1: GSTIN lookup */}
      <FieldWithAction
        label="GSTIN number"
        placeholder="Enter GSTIN number"
        hint="15 characters — e.g. 27ABCDE1234F1Z5"
        autoCapitalize="characters"
        autoComplete="off"
        spellCheck={false}
        inputMode="text"
        maxLength={15}
        value={gstinInput}
        onChange={(e) => {
          setGstinInput(e.target.value.toUpperCase());
          if (gstinError) setGstinError(null);
        }}
        error={gstinError ?? undefined}
        readOnly={gstinFetched}
        action={
          <Button
            variant="inline"
            onClick={handleVerifyGstin}
            loading={fetching}
            disabled={!gstinValid || gstinFetched}
          >
            {gstinFetched ? "Verified" : "Verify"}
          </Button>
        }
      />

      {/* Auto-filled business details from GSTIN */}
      <section className="space-y-4">
        <SectionHead icon={<Building2 />}>Business details</SectionHead>
        <div className="space-y-4">
          <TextField
            label="Company name"
            placeholder="Auto-fill after GSTIN"
            autofill
            readOnly
            {...register("companyName")}
            error={errors.companyName?.message}
          />
          <TextField
            label="PAN number"
            placeholder="Auto-fill after GSTIN"
            autofill
            readOnly
            {...register("pan")}
            error={errors.pan?.message}
          />
          <TextField
            label="Business type"
            placeholder="Auto-fill after GSTIN"
            autofill
            readOnly
            {...register("businessType")}
            error={errors.businessType?.message}
          />
          <TextField
            label="Nature of business"
            placeholder="Auto-fill after GSTIN"
            autofill
            readOnly
            {...register("natureOfBusiness")}
          />
        </div>
      </section>

      {/* Address — auto-filled from GSTIN, user can edit if different */}
      <section className="space-y-4">
        <SectionHead icon={<MapPin />}>Address</SectionHead>
        <div className="grid grid-cols-3 gap-3">
          <TextField
            label="City"
            placeholder="Auto-fill after GSTIN"
            autofill
            {...register("city")}
            error={errors.city?.message}
          />
          <TextField
            label="State"
            placeholder="Auto-fill after GSTIN"
            autofill
            {...register("state")}
            error={errors.state?.message}
          />
          <TextField
            label="Pincode"
            placeholder="Auto-fill after GSTIN"
            autofill
            inputMode="numeric"
            maxLength={6}
            {...register("pincode")}
            error={errors.pincode?.message}
          />
        </div>
        <TextField
          label="Building address"
          placeholder="Enter building address"
          {...register("building")}
          error={errors.building?.message}
        />
      </section>

      {/* Step 2: Mobile OTP + owner */}
      <section className="space-y-4">
        <SectionHead icon={<Phone />}>Contact</SectionHead>
        <FieldWithAction
          label="Mobile number"
          placeholder="Enter mobile number"
          inputMode="numeric"
          maxLength={10}
          autoComplete="tel-national"
          value={mobileInput}
          onChange={(e) => {
            const clean = e.target.value.replace(/\D/g, "").slice(0, 10);
            setMobileInput(clean);
            if (mobileError) setMobileError(null);
          }}
          readOnly={verified}
          error={mobileError ?? errors.mobile?.message}
          action={
            <Button
              variant="inline"
              onClick={handleSendOtp}
              loading={sending}
              disabled={!mobileValid || verified || !gstinFetched}
            >
              {verified ? "Verified" : "Send OTP"}
            </Button>
          }
        />
        <TextField
          label="Owner name"
          placeholder="Enter owner name"
          autoComplete="name"
          {...register("ownerName")}
          error={errors.ownerName?.message}
        />
        <TextField
          label="Email address"
          placeholder="Enter email address"
          type="email"
          optional
          autoComplete="email"
          {...register("email")}
          error={errors.email?.message}
        />
      </section>

      {submitError ? <p className="text-sm font-medium text-danger">{submitError}</p> : null}

      <Button
        type="submit"
        className="w-full"
        loading={isSubmitting}
        disabled={!gstinFetched || !verified}
      >
        Continue to dashboard <ArrowRight aria-hidden className="h-4 w-4" />
      </Button>

      {!gstinFetched ? (
        <p className="-mt-2 text-center text-xs text-mute">
          Verify your GSTIN to continue
        </p>
      ) : !verified ? (
        <p className="-mt-2 text-center text-xs text-mute">
          Verify your mobile number to enable submission
        </p>
      ) : null}

      <OtpModal
        open={otp.open}
        destination={otp.destination ?? ""}
        devHint={otp.devHint}
        onClose={() => setOtp({ open: false })}
        onVerify={handleVerify}
        onResend={handleResend}
      />
    </form>
  );
}
