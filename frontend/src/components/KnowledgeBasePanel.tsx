import { useState, useEffect } from "react";
import api from "@/lib/api";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { BookOpen, UploadCloud, Trash2, FileText } from "lucide-react";
import { format, parseISO } from "date-fns";
import { toast } from "sonner";
import { AIChatPanel } from "./AIChatPanel";

export function KnowledgeBasePanel() {
    const [docs, setDocs] = useState<any[]>([]);
    const [isUploading, setIsUploading] = useState(false);
    const [file, setFile] = useState<File | null>(null);

    const fetchDocs = async () => {
        try {
            const res = await api.get("/api/knowledge");
            setDocs(res.data);
        } catch {
            toast.error("Failed to load documents");
        }
    };

    useEffect(() => {
        fetchDocs();
    }, []);

    const handleUpload = async () => {
        if (!file) return;
        setIsUploading(true);
        const formData = new FormData();
        formData.append("file", file);

        try {
            await api.post("/api/knowledge/upload", formData, {
                headers: { "Content-Type": "multipart/form-data" }
            });
            toast.success("Document uploaded and processed");
            fetchDocs();
            setFile(null);
            const input = document.getElementById("file-upload") as HTMLInputElement;
            if (input) input.value = "";
        } catch {
            toast.error("Upload failed");
        } finally {
            setIsUploading(false);
        }
    };

    const handleDelete = async (id: number) => {
        if (!window.confirm("Delete this document? Currently active RAG prompts won't use it anymore.")) return;
        try {
            await api.delete(`/api/knowledge/${id}`);
            toast.success("Document deleted");
            setDocs(docs.filter(d => d.id !== id));
        } catch {
            toast.error("Failed to delete document");
        }
    };

    return (
        <div className="flex flex-col h-full bg-muted/10 p-6 overflow-y-auto">
            <div className="mb-8 flex items-center gap-3">
                <div className="p-3 bg-primary/10 rounded-xl">
                    <BookOpen className="w-6 h-6 text-primary" />
                </div>
                <div>
                    <h2 className="text-2xl font-bold tracking-tight text-foreground">Knowledge Base</h2>
                    <p className="text-sm text-muted-foreground mt-1">Upload files to augment the AI assistant's knowledge.</p>
                </div>
            </div>

            <div className="grid xl:grid-cols-[380px_minmax(0,1fr)] gap-6 min-h-[720px]">
                <Card className="border-border/40 shadow-sm rounded-2xl h-fit sticky top-6">
                    <CardHeader>
                        <CardTitle className="text-lg">Upload Document</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Input
                            id="file-upload"
                            type="file"
                            accept=".pdf,.docx,.txt"
                            onChange={(e) => setFile(e.target.files?.[0] || null)}
                            className="file:text-primary file:font-semibold rounded-xl text-sm"
                        />
                        <Button
                            onClick={handleUpload}
                            disabled={!file || isUploading}
                            className="w-full rounded-xl"
                        >
                            {isUploading ? "Processing..." : (
                                <><UploadCloud className="w-4 h-4 mr-2" /> Upload & Process</>
                            )}
                        </Button>
                        <ul className="text-xs text-muted-foreground list-disc pl-4 space-y-1 mt-4">
                            <li>Supported formats: PDF, DOCX, TXT</li>
                            <li>Files are chunked and embedded instantly</li>
                            <li>The AI can immediately use them in Chat</li>
                        </ul>
                    </CardContent>
                </Card>

                <div className="grid gap-6 xl:grid-rows-[auto_minmax(0,1fr)]">
                    <Card className="border-border/40 shadow-sm rounded-2xl">
                        <CardHeader>
                            <CardTitle className="text-lg">Uploaded Documents</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {docs.length === 0 ? (
                                <div className="text-center p-8 text-muted-foreground bg-muted/20 rounded-xl border border-dashed border-border/50">
                                    <FileText className="w-8 h-8 opacity-20 mx-auto mb-2" />
                                    <p className="text-sm font-medium">No documents yet.</p>
                                    <p className="text-xs mt-1">Upload one to get started.</p>
                                </div>
                            ) : (
                                <div className="divide-y divide-border/40">
                                    {docs.map(doc => (
                                        <div key={doc.id} className="py-3 flex items-center justify-between group">
                                            <div className="flex items-center gap-3 overflow-hidden">
                                                <div className="w-10 h-10 rounded-lg bg-primary/5 flex items-center justify-center flex-shrink-0">
                                                    <FileText className="w-5 h-5 text-primary/70" />
                                                </div>
                                                <div className="min-w-0">
                                                    <p className="font-semibold text-sm truncate text-foreground">{doc.filename}</p>
                                                    <p className="text-[11px] text-muted-foreground mt-0.5">
                                                        {format(parseISO(doc.uploaded_at), "MMM d, yyyy 'at' h:mm a")}
                                                    </p>
                                                </div>
                                            </div>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => handleDelete(doc.id)}
                                                className="text-destructive hover:bg-destructive/10 hover:text-destructive shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                    <div className="min-h-[520px] overflow-hidden rounded-2xl border border-border/40 bg-card shadow-sm">
                        <AIChatPanel mode="knowledge_base_rag" title="Knowledge Base Assistant" />
                    </div>
                </div>
            </div>
        </div>
    );
}
