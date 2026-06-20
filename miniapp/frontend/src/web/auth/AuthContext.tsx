import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import {
  auth,
  clearTokens,
  getAccessToken,
  getRefreshToken,
  me,
  MeResponse,
  setTokens,
  TokenPair,
  UserSummary,
} from "../api/client";

interface AuthState {
  user: UserSummary | null;
  profile: MeResponse | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  setUserAfterRegister: (user: UserSummary, tokens: TokenPair) => void;
}

const AuthContext = createContext<AuthState | null>(null);

function summaryFromProfile(p: MeResponse): UserSummary {
  return {
    id: p.user.id,
    email: p.user.email,
    email_verified: p.user.email_verified,
    has_password: true,
    has_telegram: p.user.tg_id !== null,
  };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserSummary | null>(null);
  const [profile, setProfile] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scheduleRefresh = useCallback((expiresIn: number) => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    const ms = Math.max((expiresIn - 60) * 1000, 5_000);
    refreshTimer.current = setTimeout(async () => {
      const rt = getRefreshToken();
      if (!rt) return;
      try {
        const pair = await auth.refresh(rt);
        setTokens(pair.access_token, pair.refresh_token);
        scheduleRefresh(pair.expires_in);
      } catch {
        clearTokens();
        setUser(null);
        setProfile(null);
      }
    }, ms);
  }, []);

  const refreshProfile = useCallback(async () => {
    try {
      const data = await me.get();
      setProfile(data);
      setUser(summaryFromProfile(data));
    } catch {
      /* best effort */
    }
  }, []);

  // On mount: restore session from localStorage
  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      setLoading(false);
      return;
    }

    me.get()
      .then((data) => {
        setProfile(data);
        setUser(summaryFromProfile(data));
        setLoading(false);
      })
      .catch(() => {
        const rt = getRefreshToken();
        if (!rt) {
          clearTokens();
          setLoading(false);
          return;
        }
        auth
          .refresh(rt)
          .then((pair) => {
            setTokens(pair.access_token, pair.refresh_token);
            scheduleRefresh(pair.expires_in);
            return me.get();
          })
          .then((data) => {
            setProfile(data);
            setUser(summaryFromProfile(data));
          })
          .catch(() => {
            clearTokens();
          })
          .finally(() => setLoading(false));
      });
  }, [scheduleRefresh]);

  const login = useCallback(
    async (emailAddr: string, passwordVal: string) => {
      const resp = await auth.login(emailAddr, passwordVal);
      setTokens(resp.tokens.access_token, resp.tokens.refresh_token);
      scheduleRefresh(resp.tokens.expires_in);
      setUser(resp.user);
      const data = await me.get();
      setProfile(data);
      setUser(summaryFromProfile(data));
    },
    [scheduleRefresh]
  );

  const logout = useCallback(async () => {
    const rt = getRefreshToken();
    if (rt) {
      try {
        await auth.logout(rt);
      } catch {
        /* best effort */
      }
    }
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    clearTokens();
    setUser(null);
    setProfile(null);
  }, []);

  const setUserAfterRegister = useCallback(
    (u: UserSummary, tokens: TokenPair) => {
      setTokens(tokens.access_token, tokens.refresh_token);
      scheduleRefresh(tokens.expires_in);
      setUser(u);
    },
    [scheduleRefresh]
  );

  return (
    <AuthContext.Provider
      value={{ user, profile, loading, login, logout, refreshProfile, setUserAfterRegister }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
