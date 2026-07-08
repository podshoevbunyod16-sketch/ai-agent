/**
 * Firebase Auth configuration.
 * Reads config from VITE_ env vars (set in .env.local for dev,
 * VITE_FIREBASE_* in Render dashboard for prod).
 *
 * Setup:
 * 1. https://console.firebase.google.com/ → Create project
 * 2. Project Settings → General → Your apps → Add Web app
 * 3. Copy config values to env vars
 * 4. Authentication → Sign-in method → Enable Google, Phone
 */
import { initializeApp } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithPhoneNumber,
  RecaptchaVerifier,
  signOut,
  onAuthStateChanged,
  type User,
  type ConfirmationResult,
} from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "",
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();

// Phone auth recaptcha verifier (invisible)
let recaptchaVerifier: RecaptchaVerifier | null = null;

export function initRecaptcha(containerId: string = "recaptcha-container") {
  if (recaptchaVerifier) return recaptchaVerifier;
  recaptchaVerifier = new RecaptchaVerifier(auth, containerId, {
    size: "invisible",
    callback: () => {},
  });
  return recaptchaVerifier;
}

export async function signInWithGoogle(): Promise<User> {
  const result = await signInWithPopup(auth, googleProvider);
  return result.user;
}

export async function sendPhoneOTP(phoneNumber: string): Promise<ConfirmationResult> {
  const verifier = initRecaptcha();
  return await signInWithPhoneNumber(auth, phoneNumber, verifier);
}

export async function logoutUser(): Promise<void> {
  await signOut(auth);
}

export { onAuthStateChanged, type User, type ConfirmationResult };
