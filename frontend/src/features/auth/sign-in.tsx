"use client";
import { useState } from "react";
import { supabase } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
export function SignIn() {
  const [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!supabase) return;
    setBusy(true);
    const data = new FormData(e.currentTarget);
    try {
      const { error } = await supabase.auth.signInWithPassword({
        email: String(data.get("email")),
        password: String(data.get("password")),
      });
      setMessage(
        error
          ? "Sign-in failed. Check your credentials."
          : "Signed in. You can now submit private reports.",
      );
    } catch {
      setMessage("Sign-in service is unavailable.");
    } finally {
      setBusy(false);
    }
  }
  if (!supabase)
    return (
      <p className="panel">
        Sign-in service is not configured. Add the public Supabase project URL
        and publishable key.
      </p>
    );
  return (
    <form onSubmit={submit} className="panel max-w-md space-y-5">
      <label className="block">
        Email
        <input name="email" type="email" autoComplete="email" required />
      </label>
      <label className="block">
        Password
        <input
          name="password"
          type="password"
          autoComplete="current-password"
          required
        />
      </label>
      <Button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</Button>
      <p role="status">{message}</p>
    </form>
  );
}
