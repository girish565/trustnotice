import { useCallback, useState } from "react";
// Wraps an async action with busy/error state: const [run, { busy, error }] = useAsync(fn)
export function useAsync(fn) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const run = useCallback(async (...a) => { setBusy(true); setError(""); try { return await fn(...a); } catch (e) { setError(e.message); } finally { setBusy(false); } }, [fn]);
  return [run, { busy, error }];
}
