import { useState } from "react";
import { login, register, type AuthUser } from "@/lib/auth";
import { Lock, User, ArrowRight, AlertCircle, Zap } from "lucide-react";

interface LoginPageProps {
    onLogin: (user: AuthUser) => void;
}

export function LoginPage({ onLogin }: LoginPageProps) {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [email, setEmail] = useState("");
    const [isRegisterMode, setIsRegisterMode] = useState(false);
    const [error, setError] = useState("");
    const [isLoading, setIsLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setIsLoading(true);

        try {
            const user = isRegisterMode
                ? await register(username, password, email)
                : await login(username, password);
            onLogin(user);
        } catch (err: any) {
            setError(err.message || (isRegisterMode ? "Registration failed" : "Invalid credentials"));
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#001f3f] via-[#0a2a4a] to-[#0f172a] relative overflow-hidden">
            {/* Animated background elements */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute -top-40 -right-40 w-80 h-80 bg-blue-500/8 rounded-full blur-3xl animate-pulse" />
                <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-indigo-500/8 rounded-full blur-3xl animate-pulse" style={{ animationDelay: "1s" }} />
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-cyan-500/3 rounded-full blur-3xl" />
            </div>

            <div className="relative z-10 w-full max-w-md px-6">
                {/* Logo */}
                <div className="text-center mb-10">
                    <div className="inline-flex items-center justify-center w-18 h-18 bg-white/8 backdrop-blur-md rounded-2xl border border-white/15 shadow-2xl mb-6">
                        <Zap className="w-8 h-8 text-blue-300" />
                    </div>
                    <h1 className="text-3xl font-bold text-white tracking-tight">Smartbridge</h1>
                    <p className="text-white/40 text-sm mt-1.5 font-medium tracking-wide">AI Agent Platform</p>
                </div>

                {/* Login Card */}
                <form
                    onSubmit={handleSubmit}
                    className="bg-white/[0.06] backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl p-8 space-y-6"
                    aria-label="Login form"
                >
                    <div className="text-center mb-2">
                        <h2 className="text-xl font-semibold text-white">{isRegisterMode ? "Create account" : "Welcome back"}</h2>
                        <p className="text-white/35 text-sm mt-1">{isRegisterMode ? "Register your Smartbridge account" : "Sign in to your workspace"}</p>
                    </div>

                    {error && (
                        <div
                            className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 text-red-300 px-4 py-3 rounded-xl text-sm animate-fade-up"
                            role="alert"
                        >
                            <AlertCircle size={16} className="flex-shrink-0" />
                            {error}
                        </div>
                    )}

                    <div className="space-y-4">
                        <div className="relative">
                            <User size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-white/25" />
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                placeholder="Username"
                                required
                                autoFocus
                                autoComplete="username"
                                aria-label="Username"
                                className="w-full pl-12 pr-4 py-3.5 bg-white/[0.05] border border-white/10 rounded-xl text-white placeholder:text-white/25 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all text-sm"
                            />
                        </div>

                        {isRegisterMode && (
                            <div className="relative">
                                <User size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-white/25" />
                                <input
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="Email"
                                    required
                                    autoComplete="email"
                                    aria-label="Email"
                                    className="w-full pl-12 pr-4 py-3.5 bg-white/[0.05] border border-white/10 rounded-xl text-white placeholder:text-white/25 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all text-sm"
                                />
                            </div>
                        )}

                        <div className="relative">
                            <Lock size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-white/25" />
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="Password"
                                required
                                autoComplete="current-password"
                                aria-label="Password"
                                className="w-full pl-12 pr-4 py-3.5 bg-white/[0.05] border border-white/10 rounded-xl text-white placeholder:text-white/25 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all text-sm"
                            />
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={isLoading || !username || !password || (isRegisterMode && !email)}
                        className="w-full py-3.5 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all duration-200 flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20 hover:shadow-blue-500/30 active:scale-[0.98]"
                    >
                        {isLoading ? (
                            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        ) : (
                            <>
                                {isRegisterMode ? "Register" : "Sign In"}
                                <ArrowRight size={18} />
                            </>
                        )}
                    </button>

                    <div className="text-center">
                        <p className="text-white/20 text-xs">
                            Demo: <span className="text-white/35">admin / admin123</span> or <span className="text-white/35">employee / emp123</span>
                        </p>
                    </div>
                    <div className="text-center">
                        <button
                            type="button"
                            className="text-xs text-blue-300 hover:text-blue-200 transition-colors"
                            onClick={() => {
                                setIsRegisterMode(prev => !prev);
                                setError("");
                            }}
                        >
                            {isRegisterMode ? "Already have an account? Sign in" : "Need an account? Register"}
                        </button>
                    </div>
                </form>

                <p className="text-center text-white/15 text-xs mt-8">
                    Smartbridge Platform v2.1 — Internal Use Only
                </p>
            </div>
        </div>
    );
}
