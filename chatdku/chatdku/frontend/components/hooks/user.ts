export async function getUser() {
  const res = await fetch("/dev/ant/user", { credentials: "include" });
  if (!res.ok) return null;
  return res.json() as Promise<{ eppn: string; displayName: string }>;
}

import { API_ENDPOINTS } from "@/lib/constants";

export interface UserProfile {
  name: string;
  profile: string;
}

export interface UploadedDocument {
  id: string;
  filename: string;
  uploadedAt: Date;
  size: number;
}

export class UserAPI {
  async getUserProfile(): Promise<UserProfile> {
    try {
      const response = await fetch(API_ENDPOINTS.USER, {
        method: "GET",
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error("Failed to fetch user profile");
      }

      const data = await response.json();
      return {
        name: data.name || data.username || "User",
        profile: data.profile || "",
      };
    } catch (error) {
      console.error("Error fetching user profile:", error);
      return {
        name: "User",
        profile: "",
      };
    }
  }

  async updateUserProfile(profile: string): Promise<boolean> {
    try {
      // TODO: Replace endpoint with a real new profile update API, instead of the /user API.
      const response = await fetch(API_ENDPOINTS.USER, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({ profile }),
      });

      return response.ok;
    } catch (error) {
      console.error("Error updating user profile:", error);
      return false;
    }
  }

  async uploadDocument(file: File): Promise<UploadedDocument | null> {
    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(API_ENDPOINTS.FILE_UPLOAD, {
        method: "POST",
        credentials: "include",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Failed to upload document");
      }

      const data = await response.json();
      return {
        id: data.id || Date.now().toString(),
        filename: file.name,
        uploadedAt: new Date(),
        size: file.size,
      };
    } catch (error) {
      console.error("Error uploading document:", error);
      return null;
    }
  }

  async getUploadedDocuments(): Promise<UploadedDocument[]> {
    try {
      const response = await fetch(API_ENDPOINTS.FILE_UPLOAD, {
        method: "GET",
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error("Failed to fetch documents");
      }

      const data = await response.json();
      return data.map((doc: any) => ({
        id: doc.id,
        filename: doc.filename || doc.name,
        uploadedAt: new Date(doc.uploaded_at || doc.createdAt),
        size: doc.size || 0,
      }));
    } catch (error) {
      console.error("Error fetching documents:", error);
      return [];
    }
  }

  async deleteDocument(documentId: string): Promise<boolean> {
    try {
      const response = await fetch(
        `${API_ENDPOINTS.FILE_UPLOAD}/${documentId}`,
        {
          method: "DELETE",
          credentials: "include",
        },
      );

      return response.ok;
    } catch (error) {
      console.error("Error deleting document:", error);
      return false;
    }
  }
}

export const userAPI = new UserAPI();
