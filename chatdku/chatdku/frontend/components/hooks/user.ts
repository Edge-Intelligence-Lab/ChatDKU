export async function getUser() {
  const res = await fetch("/api/user", { credentials: "include" });
  if (!res.ok) return null;
  return res.json() as Promise<{ eppn: string; displayName: string }>;
}

