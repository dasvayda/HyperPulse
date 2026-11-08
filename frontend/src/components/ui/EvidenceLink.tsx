import Link from "next/link";

export function EvidenceLink({ id }: { id?: string | null }) {
  return id ? (
    <Link href={`/evidence/${id}`} className="text-xs text-accent hover:underline">
      View evidence at signal time
    </Link>
  ) : <span className="text-xs text-text-dim">Historical evidence unavailable</span>;
}
