import DisclaimerBanner from "@/components/DisclaimerBanner";
import Footer from "@/components/Footer";
import Header from "@/components/Header";
import Hero from "@/components/Hero";
import HowItWorks from "@/components/HowItWorks";
import TestCards from "@/components/TestCards";

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <DisclaimerBanner />
      <Header />
      <main className="flex-1">
        <Hero />
        <TestCards />
        <HowItWorks />
      </main>
      <Footer />
    </div>
  );
}
