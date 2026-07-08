/**
 * LoginPage — Authentication screen with Google and Phone OTP.
 * Framer Motion animations for entrance and transitions.
 */
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { LogIn, Phone, ArrowRight, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";

export default function LoginPage() {
  const {
    signInGoogle,
    sendOTP,
    verifyOTP,
    logout,
    showOTPInput,
    error,
    loading,
  } = useAuth();
  const [phoneNumber, setPhoneNumber] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [sending, setSending] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSendOTP = async () => {
    if (!phoneNumber.trim()) {
      setLocalError("Enter phone number (+1234567890)");
      return;
    }
    setLocalError(null);
    setSending(true);
    try {
      await sendOTP(phoneNumber.trim());
    } catch (e: any) {
      setLocalError(e.message);
    }
    setSending(false);
  };

  const handleVerifyOTP = async () => {
    if (!otpCode.trim()) {
      setLocalError("Enter OTP code");
      return;
    }
    setLocalError(null);
    setVerifying(true);
    try {
      await verifyOTP(otpCode.trim());
    } catch (e: any) {
      setLocalError(e.message);
    }
    setVerifying(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900 p-4">
      <div id="recaptcha-container" />

      <motion.div
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="w-full max-w-md"
      >
        <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 p-8">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-center mb-8"
          >
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-gradient-to-br from-blue-500 to-violet-600 mb-4 shadow-lg">
              <Sparkles className="w-7 h-7 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
              AI Chat Agent
            </h1>
            <p className="text-slate-500 dark:text-slate-400 mt-1 text-sm">
              Sign in to start chatting
            </p>
          </motion.div>

          {/* Google Sign In */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 }}
          >
            <Button
              onClick={signInGoogle}
              disabled={loading}
              className="w-full h-11 text-base font-medium bg-white dark:bg-slate-800 text-slate-800 dark:text-white border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 transition-all"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
              ) : (
                <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                  <path
                    fill="currentColor"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  />
                </svg>
              )}
              Sign in with Google
            </Button>
          </motion.div>

          {/* Divider */}
          <div className="flex items-center my-6">
            <div className="flex-1 h-px bg-slate-200 dark:bg-slate-700" />
            <span className="px-3 text-xs text-slate-400 dark:text-slate-500 uppercase">
              or
            </span>
            <div className="flex-1 h-px bg-slate-200 dark:bg-slate-700" />
          </div>

          {/* Phone OTP */}
          <AnimatePresence mode="wait">
            {!showOTPInput ? (
              <motion.div
                key="phone-input"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ delay: 0.4 }}
                className="space-y-3"
              >
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <Input
                    type="tel"
                    placeholder="+1234567890"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    className="pl-10 h-11"
                  />
                </div>
                <Button
                  onClick={handleSendOTP}
                  disabled={sending}
                  className="w-full h-11 bg-blue-600 hover:bg-blue-700 text-white font-medium"
                >
                  {sending ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <ArrowRight className="w-4 h-4 mr-2" />
                  )}
                  Send SMS Code
                </Button>
              </motion.div>
            ) : (
              <motion.div
                key="otp-input"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-3"
              >
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Enter the 6-digit code sent to {phoneNumber}
                </p>
                <Input
                  type="text"
                  placeholder="123456"
                  maxLength={6}
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  className="h-11 text-center text-lg tracking-[0.5em] font-mono"
                />
                <Button
                  onClick={handleVerifyOTP}
                  disabled={verifying}
                  className="w-full h-11 bg-blue-600 hover:bg-blue-700 text-white font-medium"
                >
                  {verifying ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <LogIn className="w-4 h-4 mr-2" />
                  )}
                  Verify Code
                </Button>
                <button
                  onClick={() => {
                    setOtpCode("");
                    logout();
                  }}
                  className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 w-full text-center"
                >
                  Use different number
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Error */}
          <AnimatePresence>
            {(error || localError) && (
              <motion.p
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="text-sm text-red-600 dark:text-red-400 mt-4 text-center"
              >
                {error || localError}
              </motion.p>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  );
}
