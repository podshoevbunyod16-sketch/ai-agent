/**
 * App.tsx — Root component with routing and auth guard.
 * Routes: / (chat), /mcp-servers (MCP management).
 */
import { Routes, Route, Navigate } from "react-router";
import { useAuth } from "@/hooks/useAuth";
import LoginPage from "@/pages/LoginPage";
import ChatPage from "@/pages/ChatPage";
import MCPServersPage from "@/pages/MCPServersPage";

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <AuthGuard>
            <ChatPage />
          </AuthGuard>
        }
      />
      <Route
        path="/mcp-servers"
        element={
          <AuthGuard>
            <MCPServersPage />
          </AuthGuard>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
