import { useState, useEffect } from "react";
import { User, Mail, Bell, Shield, Save } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import api from "@/lib/api";
import type { AuthUser } from "@/lib/auth";

export function SettingsPanel({ user }: { user: AuthUser }) {
    const [preference, setPreference] = useState("email");
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);

    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const response = await api.get("/api/settings");
                if (response.data && response.data.notification_preference) {
                    setPreference(response.data.notification_preference);
                }
            } catch (err) {
                console.error("Failed to fetch settings", err);
                toast.error("Failed to load your settings.");
            } finally {
                setIsLoading(false);
            }
        };
        fetchSettings();
    }, []);

    const handleSave = async () => {
        setIsSaving(true);
        try {
            await api.put("/api/settings", { notification_preference: preference });
            toast.success("Settings saved successfully.");
        } catch (err) {
            console.error("Failed to save settings", err);
            toast.error("Failed to save your settings.");
        } finally {
            setIsSaving(false);
        }
    };

    if (isLoading) {
        return (
            <div className="flex flex-col h-full bg-muted/10 p-6 items-center justify-center">
                <div className="animate-pulse flex flex-col items-center">
                    <div className="h-10 w-10 bg-muted-foreground/20 rounded-full mb-4"></div>
                    <div className="h-4 w-32 bg-muted-foreground/20 rounded"></div>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-muted/10">
            <div className="p-6 border-b border-border/50 bg-card/80 backdrop-blur-md sticky top-0 z-10">
                <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
                <p className="text-sm text-muted-foreground mt-1">Manage your account preferences and notifications.</p>
            </div>

            <div className="flex-1 overflow-y-auto p-6 max-w-4xl mx-auto w-full space-y-6">
                <Card className="rounded-2xl border-border/40 shadow-sm overflow-hidden">
                    <CardHeader className="bg-muted/30 border-b border-border/40 pb-4">
                        <CardTitle className="text-lg flex items-center gap-2">
                            <User className="h-5 w-5 text-primary" />
                            Profile Information
                        </CardTitle>
                        <CardDescription>Your personal account details</CardDescription>
                    </CardHeader>
                    <CardContent className="p-6 grid gap-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="space-y-2">
                                <Label className="text-muted-foreground text-xs uppercase tracking-wider font-bold">Display Name</Label>
                                <div className="font-medium text-base">{user.displayName}</div>
                            </div>
                            <div className="space-y-2">
                                <Label className="text-muted-foreground text-xs uppercase tracking-wider font-bold">Username</Label>
                                <div className="font-medium text-base">{user.username}</div>
                            </div>
                            <div className="space-y-2">
                                <Label className="text-muted-foreground text-xs uppercase tracking-wider font-bold flex items-center gap-1.5">
                                    <Shield size={14} /> Role
                                </Label>
                                <div className="font-medium text-base capitalize">{user.role}</div>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="rounded-2xl border-border/40 shadow-sm overflow-hidden">
                    <CardHeader className="bg-muted/30 border-b border-border/40 pb-4">
                        <CardTitle className="text-lg flex items-center gap-2">
                            <Bell className="h-5 w-5 text-primary" />
                            Notifications
                        </CardTitle>
                        <CardDescription>Choose how you want to be notified about task updates</CardDescription>
                    </CardHeader>
                    <CardContent className="p-6">
                        <div className="space-y-4">
                            <Label className="text-base font-semibold">Preferred Channel</Label>
                            <RadioGroup value={preference} onValueChange={setPreference} className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="relative">
                                    <RadioGroupItem value="email" id="email" className="peer sr-only" />
                                    <Label
                                        htmlFor="email"
                                        className="flex flex-col items-center justify-between rounded-xl border-2 border-muted bg-transparent p-4 hover:bg-muted/50 peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-primary/5 cursor-pointer transition-all"
                                    >
                                        <Mail className="mb-3 h-6 w-6 peer-data-[state=checked]:text-primary text-muted-foreground" />
                                        <div className="font-semibold text-foreground">Email Notifications</div>
                                        <div className="text-xs text-muted-foreground mt-1">Receive updates via email</div>
                                    </Label>
                                </div>
                                <div className="relative">
                                    <RadioGroupItem value="slack" id="slack" className="peer sr-only" />
                                    <Label
                                        htmlFor="slack"
                                        className="flex flex-col items-center justify-between rounded-xl border-2 border-muted bg-transparent p-4 hover:bg-muted/50 peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-primary/5 cursor-pointer transition-all"
                                    >
                                        <div className="mb-3 h-6 w-6 flex items-center justify-center font-bold text-lg peer-data-[state=checked]:text-primary text-muted-foreground">#</div>
                                        <div className="font-semibold text-foreground">Slack Notifications</div>
                                        <div className="text-xs text-muted-foreground mt-1">Direct messages in Slack</div>
                                    </Label>
                                </div>
                            </RadioGroup>
                        </div>
                        <div className="mt-8 pt-6 border-t border-border/40 flex justify-end">
                            <Button
                                onClick={handleSave}
                                disabled={isSaving}
                                className="bg-primary hover:bg-primary/90 text-primary-foreground font-medium rounded-xl h-10 px-6 active:scale-95 transition-transform shadow-sm flex items-center gap-2"
                            >
                                {isSaving ? (
                                    <div className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                                ) : (
                                    <>
                                        <Save size={16} /> Save Preferences
                                    </>
                                )}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
