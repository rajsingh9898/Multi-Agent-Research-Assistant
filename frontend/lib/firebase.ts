"use client"

/**
 * Firebase client helpers for authentication and frontend state management.
 */

import { initializeApp, getApps, type FirebaseApp } from "firebase/app"
import {
  GoogleAuthProvider,
  type User,
  getAuth,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
  type Auth,
} from "firebase/auth"
import { getFirestore, type Firestore } from "firebase/firestore"

export type AuthenticatedUser = {
  uid: string
  email: string | null
  displayName: string | null
  photoURL: string | null
  emailVerified: boolean
}

export type BackendLoginResponse = {
  uid: string
  email: string | null
  display_name: string | null
  photo_url: string | null
  email_verified: boolean
  created_at: string | null
  last_login_at: string | null
}

export type AuthChangeHandler = (user: User | null) => void

/**
 * Firebase web config loaded from environment variables.
 */
export const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? "",
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? "",
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? "",
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET ?? "",
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID ?? "",
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID ?? "",
}

const backendBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

/**
 * Initialize and return the single Firebase app instance.
 */
export function getFirebaseApp(): FirebaseApp {
  if (!firebaseConfig.apiKey || !firebaseConfig.projectId) {
    throw new Error("Missing Firebase web config. Set NEXT_PUBLIC_FIREBASE_* variables in frontend/.env.local")
  }

  if (getApps().length > 0) {
    return getApps()[0]
  }

  return initializeApp(firebaseConfig)
}

/**
 * Return the Firebase Authentication instance.
 */
export function getFirebaseAuth(): Auth {
  return getAuth(getFirebaseApp())
}

/**
 * Return the Firestore client instance.
 */
export function getFirebaseDb(): Firestore {
  return getFirestore(getFirebaseApp())
}

/**
 * Sign in with Google and exchange the Firebase token with the backend.
 */
export async function signInWithGoogle(): Promise<{ user: AuthenticatedUser; backend: BackendLoginResponse }> {
  try {
    const auth = getFirebaseAuth()
    const provider = new GoogleAuthProvider()
    provider.setCustomParameters({ prompt: "select_account" })

    const result = await signInWithPopup(auth, provider)
    const idToken = await result.user.getIdToken()

    const response = await fetch(`${backendBaseUrl}/api/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ id_token: idToken }),
    })

    if (!response.ok) {
      const errorBody = await response.json().catch(() => null)
      throw new Error(errorBody?.detail ?? "Backend login failed")
    }

    const backend = (await response.json()) as BackendLoginResponse
    return {
      user: {
        uid: result.user.uid,
        email: result.user.email,
        displayName: result.user.displayName,
        photoURL: result.user.photoURL,
        emailVerified: result.user.emailVerified,
      },
      backend,
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "Google sign in failed"
    throw new Error(message)
  }
}

/**
 * Sign out the current Firebase user.
 */
export async function signOutUser(): Promise<void> {
  try {
    await signOut(getFirebaseAuth())
  } catch (error) {
    const message = error instanceof Error ? error.message : "Sign out failed"
    throw new Error(message)
  }
}

/**
 * Return the current Firebase ID token or null when the user is not signed in.
 */
export async function getIdToken(): Promise<string | null> {
  try {
    const user = getFirebaseAuth().currentUser
    if (!user) {
      return null
    }
    return await user.getIdToken()
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to fetch Firebase token"
    throw new Error(message)
  }
}

/**
 * Subscribe to auth state changes and return the unsubscribe function.
 */
export function onAuthChange(handler: AuthChangeHandler): () => void {
  try {
    return onAuthStateChanged(getFirebaseAuth(), handler)
  } catch (error) {
    const message = error instanceof Error ? error.message : "Auth listener failed"
    throw new Error(message)
  }
}
