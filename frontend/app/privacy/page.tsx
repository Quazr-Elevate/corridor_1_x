import type { Metadata } from "next";
import { PolicyShell } from "@/components/legal/PolicyShell";

export const metadata: Metadata = {
  title: "Privacy Policy — Corridor One X",
  description:
    "How Corridor One X collects, uses, stores, and protects your personal data under India's DPDP Act and UAE's PDPL.",
};

export default function PrivacyPage() {
  return (
    <PolicyShell
      title="Privacy Policy"
      updated="29 August 2026"
      subtitle="How Corridor One X collects, uses, stores, and protects your personal data under India's DPDP Act and UAE's PDPL."
      media="portDay"
    >
      <p className="text-fg">
        This policy explains what data Corridor One X (&quot;<b>Cor1x</b>,&quot;
        &quot;<b>we</b>,&quot; &quot;<b>us</b>&quot;) collects when you use our
        website and dashboard, why we collect it, and what rights you have over
        it. It applies whether you are in India (governed by the Digital
        Personal Data Protection Act, 2023) or the UAE (governed by Federal
        Decree-Law No. 45 of 2021).
      </p>

      <Section title="1. What we collect and why">
        <ul>
          <Li>
            <b>Mobile number</b> — required. We use it as your login ID and to
            send OTP verification codes. Stored in the <code>identities</code>{" "}
            table, encrypted at rest by our hosting provider.
          </Li>
          <Li>
            <b>Full name, email</b> — collected at signup. Used to address you
            in the product, notify you of account activity, and let admin
            support respond to your queries.
          </Li>
          <Li>
            <b>Address, alternate contacts, social links</b> — optional. You
            add these from your dashboard. They&apos;re used to complete your
            trust profile and enable buyer/seller matching.
          </Li>
          <Li>
            <b>Business identity (GSTIN, PAN, company name, business type,
            nature of business)</b> — optional; required only if you want an
            admin-issued Verified badge. Stored in <code>business_profiles</code>{" "}
            and verified against government databases where legally permitted.
          </Li>
          <Li>
            <b>Regulatory IDs (Udyam, Aadhaar, TAN)</b> — optional. Aadhaar is
            never displayed in full anywhere in our product; only the last 4
            digits are visible, per the Aadhaar Act, 2016.
          </Li>
          <Li>
            <b>Bank account (number, IFSC, holder name)</b> — required only
            for sellers who want to receive payouts. Account numbers are
            masked in every UI and API response; the full value is used only
            when initiating a payout to your bank.
          </Li>
          <Li>
            <b>Product listings</b> — data you publish about goods you offer.
            Public to signed-in verified buyers.
          </Li>
        </ul>
      </Section>

      <Section title="2. What we don&apos;t collect">
        <p>
          We don&apos;t collect health data, biometric data (other than the
          number-only Aadhaar), children&apos;s data, or precise geolocation.
          We don&apos;t use trackers or third-party analytics that identify
          you personally. We don&apos;t sell your data.
        </p>
      </Section>

      <Section title="3. How long we keep it">
        <p>
          Account data lives as long as your account does. If you delete your
          account (see §6), we immediately mask your profile fields and free
          your phone number for reuse. Business, product, and payout records
          may be retained for up to 7 years to comply with Indian tax law
          (Section 44AA of the Income Tax Act) — a soft-deleted account is
          invisible to admins by default and only surfaced for audit.
        </p>
      </Section>

      <Section title="4. Who we share with">
        <p>Three limited categories:</p>
        <ul>
          <Li>
            <b>OTP + SMS providers</b> (MSG91): receive your mobile number
            when we send a verification code. They act on our instructions
            and cannot use your data for their own purposes.
          </Li>
          <Li>
            <b>Government verification APIs</b> (Masters India for GSTIN
            search, India Post for pincode, Razorpay for IFSC): receive the
            specific identifier being verified. No profile data is sent.
          </Li>
          <Li>
            <b>Other users on the platform</b> only when you consent — when
            a verified buyer requests to see your contact details, or when
            you publish a product listing to the catalog.
          </Li>
        </ul>
        <p>
          We never share your data with advertisers, data brokers, or law
          enforcement without a valid legal order.
        </p>
      </Section>

      <Section title="5. Where your data lives">
        <p>
          Our backend runs in Singapore (Railway&apos;s <code>sin</code>{" "}
          region, on AWS <code>ap-southeast-1</code>). Data at rest is
          encrypted by the underlying storage provider (AWS EBS with
          KMS-managed keys). Data in transit uses TLS 1.2 or higher. India
          hosting is on our Phase 2 roadmap; DPDP Act §16 permits transfer
          to any country not on the Central Government&apos;s restricted
          list, and Singapore is not restricted as of this policy&apos;s
          effective date.
        </p>
      </Section>

      <Section title="6. Your rights">
        <ul>
          <Li>
            <b>Access</b> — see everything we have on you via your dashboard
            (Profile → all four tabs).
          </Li>
          <Li>
            <b>Correction</b> — edit any field from the same screen; changes
            take effect immediately.
          </Li>
          <Li>
            <b>Erasure</b> — Dashboard → Settings → Delete account. Your
            profile fields are wiped within seconds, your phone number is
            freed for reuse, and your session ends. Business and product
            records may be retained for tax compliance (see §3).
          </Li>
          <Li>
            <b>Grievance</b> — email{" "}
            <a
              href="mailto:privacy@cor1x.com"
              className="rounded-sm text-accent underline underline-offset-4"
            >
              privacy@cor1x.com
            </a>
            . Our Grievance Officer will respond within 30 days as required by
            DPDP.
          </Li>
        </ul>
      </Section>

      <Section title="7. Breach notification">
        <p>
          If we detect a personal-data breach affecting your account, we will
          notify you and the Data Protection Board of India (or the UAE Data
          Office where applicable) within 72 hours, per §8 of DPDP.
        </p>
      </Section>

      <Section title="8. Changes to this policy">
        <p>
          The effective date is at the top. If we change something material,
          we&apos;ll notify signed-in users on their next dashboard load and
          record which version of the policy you consented to (see the
          <code> consent_version </code>
          field on your profile).
        </p>
      </Section>
    </PolicyShell>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="pt-2">
      <h2 className="t-title3 text-fg">{title}</h2>
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  );
}

function Li({ children }: { children: React.ReactNode }) {
  return (
    <li className="ml-5 list-disc pl-1 marker:text-fg-3">
      <div>{children}</div>
    </li>
  );
}
