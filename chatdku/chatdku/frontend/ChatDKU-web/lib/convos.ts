import { API_ENDPOINTS } from "./constants";

export interface Message {
  role: "Bot" | "User";
  content: string;
  timestamp: string;
}

export interface Convo {
  id: string;
  title: string;
  created_at: Date;
}

export async function getNewSession(): Promise<string | null> {
  try {
    const response = await fetch(API_ENDPOINTS.NEW_SESSION, {
      credentials: "include",
    });
    if (!response.ok) {
      throw new Error("Failed to create new session");
    }
    const data = await response.json();
    return data.session_id;
  } catch (error) {
    console.error("Error creating new session:", error);
    return null;
  }
}

interface RawConversation {
  id: string;
  title?: string;
  created_at: string;
}

export async function getConversations(): Promise<Convo[]> {
  try {
    const response = await fetch(API_ENDPOINTS.CONVERSATIONS, {
      credentials: "include",
    });
    if (!response.ok) {
      throw new Error("Failed to fetch conversations");
    }
    const data: RawConversation[] = await response.json();

    return data.map((conv: RawConversation) => ({
      id: conv.id,
      title: conv.title || "New Chat", // Fallback title if none exists
      created_at: new Date(conv.created_at),
    }));
  } catch (error) {
    console.error("Error fetching conversations:", error);
    return [];
  }
}

export async function getSessionMessages(
  sessionId: string,
): Promise<Message[]> {
  try {
    const response = await fetch(API_ENDPOINTS.SESSION_MESSAGES(sessionId), {
      credentials: "include",
    });
    if (!response.ok) {
      throw new Error("Failed to fetch session messages");
    }
    const data = await response.json();

    return data.map((msg: any) => ({
      role: msg.role,
      content: msg.content,
      timestamp: msg.timestamp,
    }));
  } catch (error) {
    console.error("Error fetching session messages:", error);
    return [];
  }
}
