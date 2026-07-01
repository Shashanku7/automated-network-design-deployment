import { createContext, useContext, useState, useEffect, useCallback } from "react";

const KC = {
  url: window.location.origin,
  realm: "cx-sol-build",
  clientId: "gateway",
};

const TOKEN_KEY = "kc_access_token";
const REFRESH_KEY = "kc_refresh_token";
const VERIFIER_KEY = "kc_code_verifier";

function base64URL(buf) {
  return btoa(String.fromCharCode(...new Uint8Array(buf)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

async function generateChallenge() {
  const verifier = base64URL(crypto.getRandomValues(new Uint8Array(64)));
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  const challenge = base64URL(buf);
  return { verifier, challenge };
}

function buildLoginUrl(challenge) {
  const params = new URLSearchParams({
    client_id: KC.clientId,
    response_type: "code",
    redirect_uri: `${window.location.origin}/callback`,
    scope: "openid profile email",
    code_challenge_method: "S256",
    code_challenge: challenge,
  });
  return `${KC.url}/realms/${KC.realm}/protocol/openid-connect/auth?${params}`;
}

function buildLogoutUrl() {
  const params = new URLSearchParams({
    post_logout_redirect_uri: window.location.origin,
    id_token_hint: "", // optional, skip for simplicity
  });
  return `${KC.url}/realms/${KC.realm}/protocol/openid-connect/logout?${params}`;
}

async function exchangeCode(code, verifier) {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: KC.clientId,
    code,
    redirect_uri: `${window.location.origin}/callback`,
    code_verifier: verifier,
  });
  const res = await fetch(`${KC.url}/realms/${KC.realm}/protocol/openid-connect/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) throw new Error("Token exchange failed");
  return res.json();
}

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    if (code) {
      const verifier = sessionStorage.getItem(VERIFIER_KEY);
      sessionStorage.removeItem(VERIFIER_KEY);
      if (verifier) {
        exchangeCode(code, verifier)
          .then((data) => {
            localStorage.setItem(TOKEN_KEY, data.access_token);
            if (data.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
            setToken(data.access_token);
            window.history.replaceState(null, "", "/");
          })
          .catch((err) => {
            console.error("Token exchange failed:", err);
            window.history.replaceState(null, "", "/");
          });
      }
    }
    setReady(true);
  }, []);

  const login = useCallback(async () => {
    const { verifier, challenge } = await generateChallenge();
    sessionStorage.setItem(VERIFIER_KEY, verifier);
    window.location.href = buildLoginUrl(challenge);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    sessionStorage.removeItem(VERIFIER_KEY);
    setToken(null);
    window.location.href = buildLogoutUrl();
  }, []);

  const getToken = useCallback(() => {
    const t = localStorage.getItem(TOKEN_KEY);
    setToken(t);
    return t;
  }, []);

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: !!token,
        token,
        login,
        logout,
        getToken,
        ready,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
