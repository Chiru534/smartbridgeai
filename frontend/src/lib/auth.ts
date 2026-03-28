export type AuthUser = {
    username: string;
    displayName: string;
    role: "admin" | "employee";
    token: string;
    email?: string;
};

// ─── DEV / TEST MODE: Auth is completely bypassed ────────────────────────────
// Replace this mock user object if you need a different name/role.
const MOCK_USER: AuthUser = {
    username: "tester",
    displayName: "Tester",
    role: "admin",
    token: "dev-bypass-token",
    email: "tester@smartbridge.local",
};

export async function login(_username: string, _password: string): Promise<AuthUser> {
    return MOCK_USER;
}

export async function register(_username: string, _password: string, _email: string): Promise<AuthUser> {
    return MOCK_USER;
}

export function setUser(_user: AuthUser): void {
    // no-op in bypass mode
}

export function logout(): void {
    // no-op in bypass mode — stays "logged in" for testing
}

/** Always returns the mock user — login screen is never shown. */
export function getUser(): AuthUser {
    return MOCK_USER;
}

export function isAdmin(user: AuthUser | null): boolean {
    return user?.role === "admin";
}

export function getToken(): string | null {
    return MOCK_USER.token;
}
