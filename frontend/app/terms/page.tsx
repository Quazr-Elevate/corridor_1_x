import type { Metadata } from "next";
import { PolicyShell } from "@/components/legal/PolicyShell";

export const metadata: Metadata = {
  title: "Terms of Service — Cor1x",
  description:
    "The agreement between you and Corridor One X when you use our marketplace.",
};

export default function TermsPage() {
  return (
    <PolicyShell title="Terms of Service" updated="29 August 2026">
      <p className="text-paper">
        These Terms govern your use of Corridor One X (&quot;<b>Cor1x</b>&quot;).
        By creating an account you agree to them. If you disagree with any
        clause, don&apos;t use the service.
      </p>

      <Section title="1. What Cor1x is">
        <p>
          A verified marketplace for agricultural commodities — currently
          focused on rice — that connects producers, exporters, and importers.
          We provide identity verification and a directory. We do NOT take
          custody of goods, hold funds in escrow, sign contracts on your
          behalf, or arbitrate disputes between users.
        </p>
      </Section>

      <Section title="2. Your account">
        <ul>
          <Li>
            You must be at least 18 years old and legally able to enter into
            binding commercial agreements in your jurisdiction.
          </Li>
          <Li>
            One account per mobile number. Sharing accounts or misrepresenting
            identity is grounds for immediate termination.
          </Li>
          <Li>
            You&apos;re responsible for the accuracy of the information you
            put on your profile and product listings. Uploading a fake GSTIN,
            forged bank details, or altered documents will result in
            permanent rejection and possible legal action.
          </Li>
        </ul>
      </Section>

      <Section title="3. The verified badge">
        <p>
          An admin issues the Verified badge only after your Primary,
          Business, and Bank profile sections are complete and reviewed. We
          reserve the right to revoke it for cause — for example, if a
          document is later found to be altered, if a counterparty reports
          fraud, or if your identifiers appear on official sanction lists.
        </p>
      </Section>

      <Section title="4. Public vs private data">
        <p>
          Once you publish a product, its non-sensitive details (name,
          category, variety, quantity, price, origin state, packaging,
          photos, your company name, city, and Verified badge status) become
          visible to any signed-in verified buyer on our public catalog.
          Your phone number, email, and full address remain private until
          you consent to a specific contact-reveal.
        </p>
      </Section>

      <Section title="5. Contact reveal">
        <p>
          When a verified buyer requests to see a seller&apos;s contact
          details, Cor1x records the reveal (buyer, seller, product,
          timestamp). Both parties are notified. Neither party is under any
          obligation to transact; contact reveal is not a sale, offer, or
          contract.
        </p>
      </Section>

      <Section title="6. Fees">
        <p>
          Cor1x is currently free for Phase 1. When paid tiers launch, the
          pricing page will be published at least 30 days before charging
          begins and existing users will be given a grace period. Continuing
          to use the service after a fee schedule takes effect constitutes
          acceptance.
        </p>
      </Section>

      <Section title="7. Prohibited use">
        <ul>
          <Li>
            No scraping, automated harvesting, or reselling of Cor1x data.
          </Li>
          <Li>
            No listing of goods you don&apos;t own or can&apos;t legally
            supply (including but not limited to prohibited pesticides,
            adulterated food, or export-restricted varieties).
          </Li>
          <Li>
            No harassment, threats, or spam via the platform&apos;s messaging
            or contact-reveal features.
          </Li>
        </ul>
      </Section>

      <Section title="8. Limitation of liability">
        <p>
          Cor1x provides the platform &quot;as is.&quot; We are not liable
          for indirect, consequential, or punitive damages arising from your
          use of the service, including but not limited to disputes with
          counterparties, spoilage of goods in transit, currency
          fluctuations, or third-party service outages (MSG91, Masters India,
          Razorpay, etc.). Our maximum aggregate liability in any twelve-
          month period is capped at ₹10,000 or the amount you paid Cor1x in
          that period, whichever is greater.
        </p>
      </Section>

      <Section title="9. Governing law">
        <p>
          These Terms are governed by the laws of India. Disputes will be
          heard in the courts of Chennai, Tamil Nadu, unless mandatory
          consumer-protection law in your jurisdiction gives you a different
          venue.
        </p>
      </Section>

      <Section title="10. Contact">
        <p>
          Reach us at{" "}
          <a
            href="mailto:legal@cor1x.com"
            className="text-accent underline-offset-4 hover:underline"
          >
            legal@cor1x.com
          </a>{" "}
          for anything Terms-related. Privacy matters are best sent to{" "}
          <a
            href="mailto:privacy@cor1x.com"
            className="text-accent underline-offset-4 hover:underline"
          >
            privacy@cor1x.com
          </a>
          .
        </p>
      </Section>
    </PolicyShell>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-title text-paper mt-8">{title}</h2>
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  );
}

function Li({ children }: { children: React.ReactNode }) {
  return (
    <li className="ml-4 list-disc marker:text-accent">
      <div>{children}</div>
    </li>
  );
}
