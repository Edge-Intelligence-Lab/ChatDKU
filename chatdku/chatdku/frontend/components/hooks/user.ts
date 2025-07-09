export async function getUser() {
  const res = await fetch("/dev/ant/user", { credentials: "include" });
  if (!res.ok) return null;
  return res.json() as Promise<{ eppn: string; displayName: string }>;
}

