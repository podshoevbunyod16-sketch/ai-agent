/**
 * MCPServersPage — Manage MCP servers: add, test, toggle, delete.
 * Route: /mcp-servers
 */
import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  Plus,
  Server,
  Trash2,
  Play,
  Power,
  Loader2,
  ChevronDown,
  ChevronUp,
  Terminal,
  Globe,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import { useAPI } from "@/hooks/useAPI";
import type { MCPServer } from "@/types";

interface ServerFormData {
  name: string;
  transport_type: "stdio" | "sse";
  command: string;
  url: string;
  env_vars: string; // JSON string
}

export default function MCPServersPage() {
  const navigate = useNavigate();
  const { getToken } = useAuth();
  const { request } = useAPI();

  const [servers, setServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState<ServerFormData>({
    name: "",
    transport_type: "stdio",
    command: "",
    url: "",
    env_vars: "{}",
  });
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResults, setTestResults] = useState<Record<number, any>>({});
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);

  const loadServers = useCallback(async () => {
    try {
      const token = await getToken();
      const data = await request<{ servers: MCPServer[] }>("/api/mcp/servers", {
        token,
      });
      setServers(data.servers);
    } catch (e) {
      console.error("Failed to load MCP servers:", e);
    } finally {
      setLoading(false);
    }
  }, [getToken, request]);

  useEffect(() => {
    loadServers();
  }, [loadServers]);

  const handleAdd = async () => {
    if (!formData.name.trim()) return;
    setAdding(true);
    try {
      const token = await getToken();
      let envVars = {};
      try {
        envVars = JSON.parse(formData.env_vars);
      } catch {
        // ignore parse error, use empty
      }

      const body: any = {
        name: formData.name,
        transport_type: formData.transport_type,
        env_vars: envVars,
      };
      if (formData.transport_type === "stdio") {
        body.command = formData.command;
      } else {
        body.url = formData.url;
      }

      await request("/api/mcp/servers", {
        method: "POST",
        body,
        token,
      });

      setFormData({
        name: "",
        transport_type: "stdio",
        command: "",
        url: "",
        env_vars: "{}",
      });
      setShowAddForm(false);
      await loadServers();
    } catch (e) {
      console.error("Add server failed:", e);
    }
    setAdding(false);
  };

  const handleTest = async (server: MCPServer) => {
    setTestingId(server.id);
    try {
      const token = await getToken();
      const result = await request<any>(`/api/mcp/servers/${server.id}/test`, {
        method: "POST",
        token,
      });
      setTestResults((prev) => ({ ...prev, [server.id]: result }));
    } catch (e: any) {
      setTestResults((prev) => ({
        ...prev,
        [server.id]: { connected: false, error: e.message },
      }));
    }
    setTestingId(null);
  };

  const handleToggle = async (server: MCPServer) => {
    try {
      const token = await getToken();
      await request(`/api/mcp/servers/${server.id}/toggle`, {
        method: "POST",
        token,
      });
      await loadServers();
    } catch (e) {
      console.error("Toggle failed:", e);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this MCP server?")) return;
    try {
      const token = await getToken();
      await request(`/api/mcp/servers/${id}`, {
        method: "DELETE",
        token,
      });
      await loadServers();
    } catch (e) {
      console.error("Delete failed:", e);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white">
      {/* Header */}
      <header className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-4 py-3 flex items-center gap-3">
        <button
          onClick={() => navigate("/")}
          className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex items-center gap-2">
          <Server className="w-5 h-5 text-blue-500" />
          <h1 className="text-lg font-semibold">MCP Servers</h1>
        </div>
        <span className="text-xs text-slate-400 ml-auto">
          {servers.length} server{servers.length !== 1 ? "s" : ""}
        </span>
      </header>

      <div className="max-w-3xl mx-auto p-4 space-y-4">
        {/* Add button */}
        {!showAddForm && (
          <Button
            onClick={() => setShowAddForm(true)}
            className="w-full h-10 border-2 border-dashed border-slate-300 dark:border-slate-700 hover:border-blue-500 dark:hover:border-blue-500 text-slate-500 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 bg-transparent hover:bg-blue-50 dark:hover:bg-blue-900/10 transition-all"
          >
            <Plus className="w-4 h-4 mr-2" />
            Add MCP Server
          </Button>
        )}

        {/* Add form */}
        <AnimatePresence>
          {showAddForm && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 space-y-3 overflow-hidden"
            >
              <h3 className="font-medium text-sm">New MCP Server</h3>

              <Input
                placeholder="Name (e.g. filesystem)"
                value={formData.name}
                onChange={(e) =>
                  setFormData((p) => ({ ...p, name: e.target.value }))
                }
              />

              {/* Transport type */}
              <div className="flex gap-2">
                <button
                  onClick={() =>
                    setFormData((p) => ({ ...p, transport_type: "stdio" }))
                  }
                  className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm border transition-colors ${
                    formData.transport_type === "stdio"
                      ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300"
                      : "border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
                  }`}
                >
                  <Terminal className="w-3.5 h-3.5" />
                  STDIO
                </button>
                <button
                  onClick={() =>
                    setFormData((p) => ({ ...p, transport_type: "sse" }))
                  }
                  className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm border transition-colors ${
                    formData.transport_type === "sse"
                      ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300"
                      : "border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
                  }`}
                >
                  <Globe className="w-3.5 h-3.5" />
                  SSE
                </button>
              </div>

              {formData.transport_type === "stdio" ? (
                <Input
                  placeholder="Command: npx -y @modelcontextprotocol/server-filesystem /tmp"
                  value={formData.command}
                  onChange={(e) =>
                    setFormData((p) => ({ ...p, command: e.target.value }))
                  }
                />
              ) : (
                <Input
                  placeholder="URL: http://localhost:3001/sse"
                  value={formData.url}
                  onChange={(e) =>
                    setFormData((p) => ({ ...p, url: e.target.value }))
                  }
                />
              )}

              <Input
                placeholder='Env vars as JSON: {"NODE_PATH": "/usr/local/lib/node"}'
                value={formData.env_vars}
                onChange={(e) =>
                  setFormData((p) => ({ ...p, env_vars: e.target.value }))
                }
              />

              <div className="flex gap-2">
                <Button
                  onClick={handleAdd}
                  disabled={adding || !formData.name.trim()}
                  className="flex-1"
                >
                  {adding && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Add Server
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setShowAddForm(false)}
                >
                  Cancel
                </Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Server list */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
          </div>
        ) : servers.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            <Server className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p className="text-sm">No MCP servers configured</p>
            <p className="text-xs mt-1">
              Add a server to extend the agent with tools
            </p>
          </div>
        ) : (
          servers.map((server) => (
            <motion.div
              key={server.id}
              layout
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden"
            >
              <div className="p-4 flex items-center gap-3">
                {/* Status indicator */}
                <div
                  className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                    server.enabled
                      ? "bg-green-500"
                      : "bg-slate-300 dark:bg-slate-600"
                  }`}
                />

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-sm truncate">
                      {server.name}
                    </h3>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                        server.transport_type === "stdio"
                          ? "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400"
                          : "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400"
                      }`}
                    >
                      {server.transport_type}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 truncate mt-0.5">
                    {server.command || server.url || "No endpoint"}
                  </p>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleTest(server)}
                    disabled={testingId === server.id}
                    className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 transition-colors"
                    title="Test connection"
                  >
                    {testingId === server.id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Play className="w-3.5 h-3.5" />
                    )}
                  </button>
                  <button
                    onClick={() => handleToggle(server)}
                    className={`p-1.5 rounded-lg transition-colors ${
                      server.enabled
                        ? "text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20"
                        : "text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                    }`}
                    title={server.enabled ? "Disable" : "Enable"}
                  >
                    <Power className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() =>
                      setExpandedId(
                        expandedId === server.id ? null : server.id
                      )
                    }
                    className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 transition-colors"
                  >
                    {expandedId === server.id ? (
                      <ChevronUp className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </button>
                  <button
                    onClick={() => handleDelete(server.id)}
                    className="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-slate-400 hover:text-red-500 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Expanded: tools + test result */}
              <AnimatePresence>
                {expandedId === server.id && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden border-t border-slate-100 dark:border-slate-800"
                  >
                    <div className="p-4 space-y-3">
                      {/* Test result */}
                      {testResults[server.id] && (
                        <div
                          className={`p-3 rounded-lg text-sm ${
                            testResults[server.id].connected
                              ? "bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800"
                              : "bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800"
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            {testResults[server.id].connected ? (
                              <CheckCircle2 className="w-4 h-4 text-green-600" />
                            ) : (
                              <XCircle className="w-4 h-4 text-red-600" />
                            )}
                            <span
                              className={`font-medium ${
                                testResults[server.id].connected
                                  ? "text-green-700 dark:text-green-400"
                                  : "text-red-700 dark:text-red-400"
                              }`}
                            >
                              {testResults[server.id].connected
                                ? "Connected"
                                : "Connection failed"}
                            </span>
                          </div>
                          {testResults[server.id].error && (
                            <p className="text-xs text-red-600 mt-1 font-mono">
                              {testResults[server.id].error}
                            </p>
                          )}
                        </div>
                      )}

                      {/* Cached tools */}
                      {server.tools_cache && server.tools_cache.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-slate-500 mb-2">
                            Available Tools ({server.tools_cache.length})
                          </p>
                          <div className="space-y-1.5">
                            {server.tools_cache.map((tool: any, i: number) => (
                              <div
                                key={i}
                                className="p-2 rounded-lg bg-slate-50 dark:bg-slate-800 text-xs"
                              >
                                <p className="font-mono font-medium text-slate-700 dark:text-slate-300">
                                  {tool.name}
                                </p>
                                <p className="text-slate-500 mt-0.5">
                                  {tool.description}
                                </p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Command/URL detail */}
                      <div className="text-xs text-slate-500 space-y-1">
                        {server.command && (
                          <p>
                            <span className="font-medium">Command:</span>{" "}
                            <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">
                              {server.command}
                            </code>
                          </p>
                        )}
                        {server.url && (
                          <p>
                            <span className="font-medium">URL:</span>{" "}
                            <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">
                              {server.url}
                            </code>
                          </p>
                        )}
                        {server.env_vars &&
                          Object.keys(server.env_vars).length > 0 && (
                            <p>
                              <span className="font-medium">Env:</span>{" "}
                              <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">
                                {JSON.stringify(server.env_vars)}
                              </code>
                            </p>
                          )}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
}
