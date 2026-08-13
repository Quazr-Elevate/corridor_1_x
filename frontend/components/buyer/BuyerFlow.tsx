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
import { api } from "@/lib/api";
import { buyerSchema, phoneRegex, type BuyerValues } from "@/lib/validation";
import { COUNTRIES } from "./countries";

interface Props {
  onComplete: (payload: BuyerValues) => void;
}

export function BuyerFlow({ onComplete }: Props) {
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

  const mobileValid = phoneRegex.test(mobileInput.trim());

  const form = useForm<BuyerValues>({
    resolver: zodResolver(buyerSchema),
    mode: "onBlur",
    defaultValues: {
      fullName: "",
      companyName: "",
      country: "India",
      city: "",
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

  const onValid = async (values: BuyerValues) => {
    setSubmitError(null);
    try {
      await api.submitBuyer(values);
      onComplete(values);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Something went wrong");
    }
  };

  return (
    <form onSubmit={handleSubmit(onValid)} className="space-y-6" noValidate>
      <section className="space-y-4">
        <SectionHead icon={<Building2 />}>About you</SectionHead>
        <TextField
          label="Full name"
          placeholder="Enter your full name"
          autoComplete="name"
          {...register("fullName")}
          error={errors.fullName?.message}
        />
        <TextField
          label="Company name"
          placeholder="Enter company name"
          autoComplete="organization"
          {...register("companyName")}
          error={errors.companyName?.message}
        />
      </section>

      <section className="space-y-4">
        <SectionHead icon={<MapPin />}>Location</SectionHead>
        <div>
          <label htmlFor="f-country" className="field-label">
            Country
          </label>
          <select
            id="f-country"
            className="field appearance-none"
            {...register("country")}
            aria-invalid={errors.country ? true : undefined}
          >
            {COUNTRIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          {errors.country ? (
            <span className="field-error" role="alert">
              {errors.country.message}
            </span>
          ) : null}
        </div>
        <TextField
          label="City"
          placeholder="Enter city"
          optional
          {...register("city")}
          error={errors.city?.message}
        />
      </section>

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
              disabled={!mobileValid || verified}
            >
              {verified ? "Verified" : "Send OTP"}
            </Button>
          }
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

      <Button type="submit" className="w-full" loading={isSubmitting} disabled={!verified}>
        Continue to dashboard <ArrowRight aria-hidden className="h-4 w-4" />
      </Button>

      {!verified ? (
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
