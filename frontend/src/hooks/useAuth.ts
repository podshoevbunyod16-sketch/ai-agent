/**
 * useAuth hook — Firebase authentication state management.
 * Handles: Google sign-in, Phone OTP, logout, token refresh.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import type { User as FirebaseUser, ConfirmationResult } from "firebase/auth";
import {
  auth,
  signInWithGoogle,
  sendPhoneOTP,
  logoutUser,
  onAuthStateChanged,
} from "@/lib/firebase";
import type { User } from "@/types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function useAuth() {
  const [firebaseUser, setFirebaseUser] = useState<FirebaseUser | null>(null);
  const [dbUser, setDbUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showOTPInput, setShowOTPInput] = useState(false);
  const confirmationResultRef = useRef<ConfirmationResult | null>(null);

  // Listen to Firebase auth state
  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async (user) => {
      setFirebaseUser(user);
      if (user) {
        try {
          const token = await user.getIdToken();
          const res = await fetch(`${API_URL}/api/auth/me`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (res.ok) {
            const data = await res.json();
            setDbUser(data);
          }
        } catch (e) {
          console.error("Failed to fetch user:", e);
        }
      } else {
        setDbUser(null);
      }
      setLoading(false);
    });
    return unsub;
  }, []);

  // Get fresh Firebase token
  const getToken = useCallback(async (): Promise<string | null> => {
    if (!firebaseUser) return null;
    return await firebaseUser.getIdToken(true);
  }, [firebaseUser]);

  // Google sign in
  const signInGoogle = useCallback(async () => {
    setError(null);
    try {
      await signInWithGoogle();
    } catch (e: any) {
      setError(e.message || "Google sign-in failed");
    }
  }, []);

  // Send phone OTP
  const sendOTP = useCallback(async (phoneNumber: string) => {
    setError(null);
    try {
      const cr = await sendPhoneOTP(phoneNumber);
      confirmationResultRef.current = cr;
      setShowOTPInput(true);
    } catch (e: any) {
      setError(e.message || "Failed to send OTP");
    }
  }, []);

  // Verify OTP
  const verifyOTP = useCallback(async (code: string) => {
    setError(null);
    if (!confirmationResultRef.current) {
      setError("No OTP sent. Request a new code.");
      return;
    }
    try {
      await confirmationResultRef.current.confirm(code);
      setShowOTPInput(false);
      confirmationResultRef.current = null;
    } catch (e: any) {
      setError(e.message || "Invalid OTP code");
    }
  }, []);

  // Logout
  const logout = useCallback(async () => {
    setError(null);
    try {
      await logoutUser();
      setDbUser(null);
      setFirebaseUser(null);
    } catch (e: any) {
      setError(e.message || "Logout failed");
    }
  }, []);

  return {
    user: firebaseUser,
    dbUser,
    loading,
    error,
    showOTPInput,
    signInGoogle,
    sendOTP,
    verifyOTP,
    logout,
    getToken,
    isAuthenticated: !!firebaseUser,
  };
}
