"use client";

import type React from "react";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Upload,
  FileText,
  Trash2,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";
import { userAPI, type UploadedDocument } from "@/components/hooks/user";
import { cn } from "./utils";

interface DocumentManagerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DocumentManager({ open, onOpenChange }: DocumentManagerProps) {
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      loadDocuments();
    }
  }, [open]);

  const loadDocuments = async () => {
    setIsLoading(true);
    try {
      // const docs = await userAPI.getUploadedDocuments();
      // setDocuments(docs);
    } catch (error) {
      setError("Failed to load documents");
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    const file = files[0];

    // Validate file type
    if (file.type !== "application/pdf") {
      setError("Only PDF files are supported");
      return;
    }

    // Validate file size (10MB limit)
    if (file.size > 10 * 1024 * 1024) {
      setError("File size must be less than 10MB");
      return;
    }

    setError(null);
    setSuccess(null);
    setUploadProgress(0);

    // Simulate upload progress
    const progressInterval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 90) {
          clearInterval(progressInterval);
          return 90;
        }
        return prev + 10;
      });
    }, 100);

    try {
      const uploadedDoc = await userAPI.uploadDocument(file);
      clearInterval(progressInterval);
      setUploadProgress(100);

      if (uploadedDoc) {
        setDocuments((prev) => [uploadedDoc, ...prev]);
        setSuccess(`Successfully uploaded ${file.name}`);
        setTimeout(() => {
          setUploadProgress(0);
          setSuccess(null);
        }, 2000);
      } else {
        setError("Failed to upload document");
        setUploadProgress(0);
      }
    } catch (error) {
      clearInterval(progressInterval);
      setError("Failed to upload document");
      setUploadProgress(0);
    }
  };

  const handleDeleteDocument = async (documentId: string, filename: string) => {
    try {
      const success = await userAPI.deleteDocument(documentId);
      if (success) {
        setDocuments((prev) => prev.filter((doc) => doc.id !== documentId));
        setSuccess(`Successfully deleted ${filename}`);
        setTimeout(() => setSuccess(null), 2000);
      } else {
        setError("Failed to delete document");
      }
    } catch (error) {
      setError("Failed to delete document");
    }
  };

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragIn = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  }, []);

  const handleDragOut = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    handleFileUpload(e.dataTransfer.files);
  }, []);

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return (
      Number.parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Document Manager
          </DialogTitle>
          <DialogDescription>
            Upload PDF documents to be used as additional context for your
            conversations.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 space-y-6 overflow-scroll">
          {/* Upload Area */}
          <Card
            className={cn(
              "border-2 border-dashed transition-colors cursor-pointer",
              dragActive
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-primary/50",
            )}
            onDragEnter={handleDragIn}
            onDragLeave={handleDragOut}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => document.getElementById("file-upload")?.click()}
          >
            <CardContent className="flex flex-col items-center space-x-2 justify-center p-4 text-center py-1">
              <div className="flex flex-row space-x-2 items-center mb-2">
                <Upload className="h-6 w-6 text-muted-foreground" />
                <h3 className="text-md sm:text-lg font-semibold ">
                  Upload PDF Documents
                </h3>
              </div>
              <div>
                <p className="text-muted-foreground text-sm mb-4 text-pretty">
                  Drag and drop your PDF files here, or click to browse. Maximum
                  file size: 10MB
                </p>
                <Button variant="outline">
                  <Upload className="h-4 w-4" />
                  Choose Files
                </Button>
                <input
                  id="file-upload"
                  type="file"
                  accept=".pdf"
                  onChange={(e) => handleFileUpload(e.target.files)}
                  className="hidden"
                />
              </div>
            </CardContent>
          </Card>

          {/* Upload Progress */}
          {uploadProgress > 0 && (
            <Card>
              <CardContent className="p-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span>Uploading...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <Progress value={uploadProgress} className="w-full" />
                </div>
              </CardContent>
            </Card>
          )}

          {/* Status Messages */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {success && (
            <Alert className="border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200">
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>{success}</AlertDescription>
            </Alert>
          )}

          {/* Documents List */}
          <Card className="flex-1">
            <CardHeader>
              <CardTitle className="text-lg">
                Uploaded Documents ({documents.length})
              </CardTitle>
              <CardDescription>
                These documents are available as context for your AI
                conversations
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0 ">
              <ScrollArea className="h-[20vh]">
                {isLoading ? (
                  <div className="flex items-center justify-center p-4">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                  </div>
                ) : documents.length > 0 ? (
                  <div className="space-y-2 p-4">
                    {documents.map((doc) => (
                      <div
                        key={doc.id}
                        className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
                      >
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <FileText className="h-5 w-5 text-red-500 shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="font-medium truncate">
                              {doc.filename}
                            </p>
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                              <span>{formatFileSize(doc.size)}</span>
                              <span>{doc.uploadedAt.toLocaleDateString()}</span>
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="secondary" className="text-xs">
                            PDF
                          </Badge>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() =>
                              handleDeleteDocument(doc.id, doc.filename)
                            }
                            className="text-muted-foreground hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center p-4 text-center">
                    <FileText className="h-12 w-12 text-muted-foreground mb-4" />
                    <p className="text-muted-foreground">
                      No documents uploaded yet
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      Upload PDF files to enhance your AI conversations
                    </p>
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>
      </DialogContent>
    </Dialog>
  );
}
