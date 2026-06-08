"use client"

/**
 * Authentication button that switches between Google sign-in and user controls.
 */

import { useEffect, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { toast } from "react-hot-toast"
import { User } from "firebase/auth"

import { onAuthChange, signInWithGoogle, signOutUser } from "../lib/firebase"

export type AuthButtonState = {
  user: User | null
  loading: boolean
}

/**
 * Render a Google sign-in button or the signed-in user state.
 */
export default function AuthButton() {
  const [state, setState] = useState<AuthButtonState>({ user: null, loading: true })
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    /** Subscribe to Firebase auth changes and keep the UI in sync. */
    const unsubscribe = onAuthChange((user) => {
      setState({ user, loading: false })
    })

    return () => unsubscribe()
  }, [])

  /** Handle Google sign in and show user feedback. */
  const handleSignIn = async () => {
    try {
      setBusy(true)
      const result = await signInWithGoogle()
      toast.success(`Welcome, ${result.user.displayName ?? result.user.email ?? "researcher"}`)
    } catch (error) {
      const message = error instanceof Error ? error.message : "Sign in failed"
      toast.error(message)
    } finally {
      setBusy(false)
    }
  }

  /** Sign the user out and reset the authenticated UI state. */
  const handleSignOut = async () => {
    try {
      setBusy(true)
      await signOutUser()
      toast.success("Signed out")
    } catch (error) {
      const message = error instanceof Error ? error.message : "Sign out failed"
      toast.error(message)
    } finally {
      setBusy(false)
    }
  }

  if (state.loading) {
    return (
      <div className="inline-flex h-11 items-center justify-center rounded-full border border-slate-200/70 bg-white/80 px-4 text-sm text-slate-500 shadow-sm backdrop-blur">
        Loading account...
      </div>
    )
  }

  return (
    <AnimatePresence mode="wait">
      {!state.user ? (
        <motion.button
          key="sign-in"
          whileHover={{ y: -1 }}
          whileTap={{ scale: 0.98 }}
          onClick={handleSignIn}
          disabled={busy}
          className="inline-flex h-11 items-center gap-2 rounded-full bg-slate-950 px-4 text-sm font-medium text-white shadow-lg shadow-slate-950/10 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70"
        >
          {busy ? (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          ) : (
            <GoogleIcon />
          )}
          Sign in with Google
        </motion.button>
      ) : (
        <motion.div
          key="signed-in"
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          className="flex flex-wrap items-center gap-3 rounded-full border border-slate-200 bg-white/90 px-3 py-2 shadow-sm backdrop-blur"
        >
          <div className="flex items-center gap-3 pr-1">
            <img
              src={state.user.photoURL || "https://www.gravatar.com/avatar/?d=mp"}
              alt={state.user.displayName || state.user.email || "Signed in user"}
              className="h-8 w-8 rounded-full border border-slate-200 object-cover"
            />
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-slate-900">
                {state.user.displayName || state.user.email || "Signed in"}
              </div>
              <div className="truncate text-xs text-slate-500">Google account connected</div>
            </div>
          </div>

          <button
            type="button"
            onClick={handleSignOut}
            disabled={busy}
            className="inline-flex h-9 items-center justify-center rounded-full bg-slate-100 px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {busy ? "Signing out..." : "Sign out"}
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

/**
 * Inline Google logo used for the sign-in button.
 */
function GoogleIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4">
      <path fill="#EA4335" d="M12 10.2v3.95h5.62c-.24 1.28-.95 2.37-2.02 3.1v2.58h3.26c1.91-1.76 3.01-4.36 3.01-7.46 0-.72-.07-1.41-.2-2.06H12Z" />
      <path fill="#34A853" d="M12 22c2.73 0 5.02-.9 6.69-2.43l-3.26-2.58c-.9.61-2.05.97-3.43.97-2.64 0-4.88-1.78-5.68-4.18H2.93v2.64C4.59 19.98 8.02 22 12 22Z" />
      <path fill="#4A90E2" d="M6.32 13.78A6.8 6.8 0 0 1 5.96 12c0-.62.1-1.22.28-1.78V7.58H2.93A9.97 9.97 0 0 0 2 12c0 1.6.38 3.12 1.05 4.42l3.27-2.64Z" />
      <path fill="#FBBC05" d="M12 5.1c1.49 0 2.83.51 3.88 1.5l2.91-2.91C17.01 1.99 14.73 1 12 1 8.02 1 4.59 3.02 2.93 6.42l3.39 2.64C7.12 6.88 9.36 5.1 12 5.1Z" />
    </svg>
  )
}
