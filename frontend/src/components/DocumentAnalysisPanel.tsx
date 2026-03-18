import { useMemo, useState } from "react";
import { toast } from "sonner";
import { FileSearch, RefreshCw, UploadCloud } from "lucide-react";

import api from "@/lib/api";
import { AIChatPanel } from "./AIChatPanel";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";

type SessionDocument = {
    filename: string;
    chunk_count: number;
    uploaded_at: string;
};

function createDocumentSessionId(): string {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
        return crypto.randomUUID();
    }
    return `doc-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function DocumentAnalysisPanel() {
    const [documentSessionId, setDocumentSessionId] = useState(createDocumentSessionId);
    const [documents, setDocuments] = useState<SessionDocument[]>([]);
    const [files, setFiles] = useState<File[]>([]);
    const [isUploading, setIsUploading] = useState(false);

    const workspaceOptions = useMemo(() => ({ document_session_id: documentSessionId }), [documentSessionId]);

    const handleUpload = async () => {
        if (files.length === 0) return;
        setIsUploading(true);
        const formData = new FormData();
        files.forEach((file) => formData.append("files", file));

        try {
            const res = await api.post(`/api/document-analysis/upload?session_id=${encodeURIComponent(documentSessionId)}`, formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            setDocuments(Array.isArray(res.data.documents) ? res.data.documents : []);
            setFiles([]);
            const input = document.getElementById("doc-analysis-upload") as HTMLInputElement | null;
            if (input) input.value = "";
            toast.success("Session documents uploaded");
        } catch {
            toast.error("Document analysis upload failed");
        } finally {
            setIsUploading(false);
        }
    };

    const resetSession = async () => {
        try {
            await api.delete(`/api/document-analysis/${encodeURIComponent(documentSessionId)}`);
        } catch {
            // Ignore cleanup failures on reset.
        }
        const nextSessionId = createDocumentSessionId();
        setDocumentSessionId(nextSessionId);
        setDocuments([]);
        setFiles([]);
        const input = document.getElementById("doc-analysis-upload") as HTMLInputElement | null;
        if (input) input.value = "";
        toast.success("Started a fresh document analysis session");
    };

    return (
        <div className="flex flex-col h-full bg-muted/10 p-6 overflow-y-auto">
            <div className="mb-8 flex items-center gap-3">
                <div className="p-3 bg-primary/10 rounded-xl">
                    <FileSearch className="w-6 h-6 text-primary" />
                </div>
                <div>
                    <h2 className="text-2xl font-bold tracking-tight text-foreground">Document Analysis</h2>
                    <p className="text-sm text-muted-foreground mt-1">Upload session-only files, then question them without persisting them into the long-term knowledge base.</p>
                </div>
            </div>

            <div className="grid xl:grid-cols-[360px_minmax(0,1fr)] gap-6 min-h-[720px]">
                <Card className="border-border/40 shadow-sm rounded-2xl h-fit">
                    <CardHeader>
                        <CardTitle className="text-lg">Session Files</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="rounded-xl border border-border/50 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
                            Session ID: <span className="font-mono text-foreground">{documentSessionId}</span>
                        </div>
                        <Input
                            id="doc-analysis-upload"
                            type="file"
                            multiple
                            accept=".pdf,.docx,.txt"
                            onChange={(event) => setFiles(Array.from(event.target.files || []))}
                            className="file:text-primary file:font-semibold rounded-xl text-sm"
                        />
                        <div className="flex gap-2">
                            <Button onClick={handleUpload} disabled={files.length === 0 || isUploading} className="flex-1 rounded-xl">
                                {isUploading ? "Processing..." : (
                                    <>
                                        <UploadCloud className="w-4 h-4 mr-2" />
                                        Upload Files
                                    </>
                                )}
                            </Button>
                            <Button variant="outline" onClick={resetSession} className="rounded-xl">
                                <RefreshCw className="w-4 h-4 mr-2" />
                                Reset
                            </Button>
                        </div>
                        <div className="space-y-2">
                            {documents.length === 0 ? (
                                <div className="rounded-xl border border-dashed border-border/50 bg-muted/20 p-4 text-sm text-muted-foreground">
                                    No session files yet.
                                </div>
                            ) : (
                                documents.map((document) => (
                                    <div key={`${document.filename}-${document.uploaded_at}`} className="rounded-xl border border-border/40 bg-card px-3 py-2">
                                        <p className="text-sm font-semibold text-foreground">{document.filename}</p>
                                        <p className="text-xs text-muted-foreground">{document.chunk_count} chunks</p>
                                    </div>
                                ))
                            )}
                        </div>
                    </CardContent>
                </Card>

                <div className="overflow-hidden rounded-2xl border border-border/40 bg-card shadow-sm">
                    <AIChatPanel
                        mode="document_analysis"
                        workspaceOptions={workspaceOptions}
                        title="Document Analysis Assistant"
                    />
                </div>
            </div>
        </div>
    );
}
