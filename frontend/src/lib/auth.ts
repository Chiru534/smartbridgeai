export type AuthUser = {
    username: string;
    displayName: string;
    role: "admin" | "employee";
    token: string;
    email?: string;
};

const AUTH_KEY = "sb_auth_user";

export async function login(username: string, password: string): Promise<AuthUser> {
    const res = await fetch("http://localhost:8000/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Login failed" }));
        throw new Error(err.detail || "Invalid credentials");
    }

    const data: AuthUser = await res.json();
    setUser(data);
    return data;
}

export async function register(username: string, password: string, email: string): Promise<AuthUser> {
    const res = await fetch("http://localhost:8000/api/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, email }),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Registration failed" }));
        throw new Error(err.detail || "Registration failed");
    }

    const data: AuthUser = await res.json();
    setUser(data);
    return data;
}

export function setUser(user: AuthUser): void {
    localStorage.setItem(AUTH_KEY, JSON.stringify(user));
}

export function logout(): void {
    localStorage.removeItem(AUTH_KEY);
    const keysToRemove: string[] = [];
    for (let index = 0; index < localStorage.length; index += 1) {
        const key = localStorage.key(index);
        if (!key) continue;
        if (key.startsWith("smartbridge_active_chat_session_") || key.startsWith("smartbridge_chat_last_activity_")) {
            keysToRemove.push(key);
        }
    }
    keysToRemove.forEach((key) => localStorage.removeItem(key));
}

export function getUser(): AuthUser | null {
    try {
        const raw = localStorage.getItem(AUTH_KEY);
        if (!raw) return null;
        return JSON.parse(raw) as AuthUser;
    } catch {
        return null;
    }
}

export function isAdmin(user: AuthUser | null): boolean {
    return user?.role === "admin";
}

export function getToken(): string | null {
    const user = getUser();
    return user?.token || null;
}
