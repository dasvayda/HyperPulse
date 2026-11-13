/** Shared beta login, deliberately separate from the backend service token. */
export async function matchesBetaLogin(header: string | null, password: string): Promise<boolean> {
  if (!password || !header || header.length > 4096 || !header.startsWith("Basic ")) return false;
  try {
    const encoder = new TextEncoder();
    const supplied = Uint8Array.from(atob(header.slice(6)), (char) => char.charCodeAt(0));
    const [actual, expected] = await Promise.all([
      crypto.subtle.digest("SHA-256", supplied),
      crypto.subtle.digest("SHA-256", encoder.encode(`beta:${password}`)),
    ]);
    const a = new Uint8Array(actual);
    const b = new Uint8Array(expected);
    let difference = 0;
    for (let i = 0; i < a.length; i++) difference |= a[i] ^ b[i];
    return difference === 0;
  } catch {
    return false;
  }
}
