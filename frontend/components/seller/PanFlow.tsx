"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, PencilLine } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { FieldWithAction } from "@/components/ui/FieldWithAction";
import { OtpModal } from "@/components/ui/OtpModal";
import { SectionHead } from "@/components/ui/SectionHead";
import { TextField } from "@/components/ui/TextField";
import { api } from "@/lib/api";
import {
  panRegex,
  phoneRegex,
  sellerPanSchema,
  type SellerPanValues,
} from "@/lib/validation";

interface Props {
  onComplete: (payload: SellerPanValues) => void;
}

const stackVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.07, delayChildren: 0.08 } },
};
const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  },
};
const revealVariants = {
  hidden: { opacity: 0, y: 14 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] },
  },
};

export function PanFlow({ onComplete }: Props) {
  const [panInput, setPanInput] = useState("");
  const [panError, setPanError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(false);
  const [panFetched, setPanFetched] = useState(false);

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

  const panValid = panRegex.test(panInput.trim().toUpperCase());
  const mobileValid = phoneRegex.test(mobileInput.trim());

  const form = useForm<SellerPanValues>({
    resolver: zodResolver(sellerPanSchema),
    mode: "onBlur",
    defaultValues: {
      pan: "",
      ownerName: "",
      companyName: "",
      building: "",
      pincode: "",
      city: "",
      state: "",
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

  const handleFetchPan = async () => {
    setPanError(null);
    const pan = panInput.trim().toUpperCase();
    if (!panRegex.test(pan)) {
      setPanError("Enter a valid 10-character PAN");
      return;
    }
    setFetching(true);
    try {
      const data = await api.lookupPan(pan);
      setValue("pan", data.pan);
      setValue("ownerName", data.name);
      setPanFetched(true);
    } catch (err) {
      setPanError(err instanceof Error ? err.message : "Could not fetch PAN details");
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
    await api.sendOtp({
      channel: "phone",
      value: mobileInput.trim(),
      purpose: "phone",
    });
  };

  const onValid = async (values: SellerPanValues) => {
    setSubmitError(null);
    try {
      await api.submitSeller({ ...values, onboardingPath: "pan" });
      onComplete(values);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Something went wrong");
    }
  };

  return (
    <form onSubmit={handleSubmit(onValid)} className="space-y-6" noValidate>
      <FieldWithAction
        label="PAN number"
        placeholder="Enter PAN number"
        hint="10 characters — e.g. ABCDE1234F"
        autoCapitalize="characters"
        autoComplete="off"
        spellCheck={false}
        maxLength={10}
        value={panInput}
        onChange={(e) => {
          setPanInput(e.target.value.toUpperCase());
          if (panError) setPanError(null);
        }}
        error={panError ?? undefined}
        readOnly={panFetched}
        action={
          <Button
            variant="inline"
            onClick={handleFetchPan}
            loading={fetching}
            disabled={!panValid || panFetched}
            data-verified={panFetched || undefined}
          >
            {panFetched ? "Fetched" : "Fetch"}
          </Button>
        }
      />

      <AnimatePresence>
        {!panFetched && (
          <motion.p
            className="flex items-center gap-2 rounded-lg border border-dashed border-line px-3 py-2.5 text-xs text-paper-muted"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.3 }}
          >
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent/70" />
            Enter your PAN and tap <span className="text-paper">Fetch</span> —
            we&apos;ll match it against your identity.
          </motion.p>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {panFetched && (
          <motion.div
            className="space-y-6"
            initial="hidden"
            animate="visible"
            exit="hidden"
            variants={stackVariants}
          >
            <motion.div variants={itemVariants}>
              <TextField
                label="Name"
                placeholder="Auto-fill after PAN"
                autofill
                readOnly
                {...register("ownerName")}
                error={errors.ownerName?.message}
              />
            </motion.div>

            <motion.section className="space-y-4" variants={revealVariants}>
              <SectionHead icon={<PencilLine />}>Fill manually</SectionHead>

              <motion.div
                className="space-y-4"
                variants={stackVariants}
                initial="hidden"
                animate="visible"
              >
                <motion.div variants={itemVariants}>
                  <TextField
                    label="Company name"
                    placeholder="Enter company name"
                    autoComplete="organization"
                    {...register("companyName")}
                    error={errors.companyName?.message}
                  />
                </motion.div>

                <motion.div
                  className="grid grid-cols-1 gap-3 sm:grid-cols-3"
                  variants={itemVariants}
                >
                  <TextField
                    label="City"
                    placeholder="City"
                    {...register("city")}
                    error={errors.city?.message}
                  />
                  <TextField
                    label="State"
                    placeholder="State"
                    {...register("state")}
                    error={errors.state?.message}
                  />
                  <TextField
                    label="Pincode"
                    placeholder="Pincode"
                    inputMode="numeric"
                    maxLength={6}
                    {...register("pincode")}
                    error={errors.pincode?.message}
                  />
                </motion.div>

                <motion.div variants={itemVariants}>
                  <TextField
                    label="Building address"
                    placeholder="Enter building address"
                    {...register("building")}
                    error={errors.building?.message}
                  />
                </motion.div>

                <motion.div variants={itemVariants}>
                  <TextField
                    label="Email address"
                    placeholder="Enter email address"
                    type="email"
                    optional
                    autoComplete="email"
                    {...register("email")}
                    error={errors.email?.message}
                  />
                </motion.div>

                <motion.div variants={itemVariants}>
                  <FieldWithAction
                    label="Mobile number"
                    placeholder="Enter mobile number"
                    inputMode="numeric"
                    maxLength={10}
                    autoComplete="tel-national"
                    value={mobileInput}
                    onChange={(e) => {
                      const clean = e.target.value
                        .replace(/\D/g, "")
                        .slice(0, 10);
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
                        data-verified={verified || undefined}
                      >
                        {verified ? "Verified" : "Send OTP"}
                      </Button>
                    }
                  />
                </motion.div>
              </motion.div>
            </motion.section>
          </motion.div>
        )}
      </AnimatePresence>

      {submitError ? (
        <motion.p
          className="text-sm font-medium text-danger"
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
        >
          {submitError}
        </motion.p>
      ) : null}

      <Button
        type="submit"
        className="w-full"
        loading={isSubmitting}
        disabled={!panFetched || !verified}
      >
        Continue to dashboard <ArrowRight aria-hidden className="h-4 w-4" />
      </Button>

      {!panFetched || !verified ? (
        <p className="-mt-2 text-center text-xs text-paper-muted">
          {!panFetched
            ? "Fetch PAN details to continue"
            : "Verify mobile number to enable submission"}
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
