import Link from "next/link";

export default function BriefNotFound() {
  return <div>
    <h1 className="text-2xl font-semibold">Published brief unavailable</h1>
    <p className="mt-3 text-text-muted">Check the address or choose another published session.</p>
    <Link href="/briefs" className="mt-5 inline-block text-accent">Browse market briefs →</Link>
  </div>;
}
