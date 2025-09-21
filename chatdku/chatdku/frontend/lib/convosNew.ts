import { API_ENDPOINTS } from './constants';

// Session management utilities
const SESSION_STORAGE_KEY = 'chatdku_session_id';
const ENDPOINT_STORAGE_KEY = 'chatdku_api_endpoint';

export interface SessionResponse {
  session_id: string;
}

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

interface RawConversation {
  id: string;
  title?: string;
  created_at: string;
}

/**
 * Get a new session from the backend
 */
export async function getNewSession(): Promise<string | null> {
  try {
    const response = await fetch(API_ENDPOINTS.NEW_SESSION, {
      method: 'GET',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      console.error('Failed to get new session:', response.status, response.statusText);
      return null;
    }

    const data: SessionResponse = await response.json();
    const sessionId = data.session_id;
    
    if (sessionId) {
      // Store session_id in localStorage
      localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
      console.log('New session created and stored:', sessionId);
    }
    
    return sessionId;
  } catch (error) {
    console.error('Error getting new session:', error);
    return null;
  }
}

/**
 * Get the current session ID from storage
 */
export function getCurrentSessionId(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(SESSION_STORAGE_KEY);
}

/**
 * Set the current session ID in storage
 */
export function setCurrentSessionId(sessionId: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
}

/**
 * Clear the current session ID from storage
 */
export function clearSessionId(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(SESSION_STORAGE_KEY);
}

/**
 * Get session messages from the backend
 */
export async function getSessionMessages(sessionId: string): Promise<Message[]> {
  try {
    const response = await fetch(API_ENDPOINTS.SESSION_MESSAGES(sessionId), {
      method: 'GET',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      console.error('Failed to get session messages:', response.status, response.statusText);
      return [];
    }

    const data = await response.json();

    return data.map((msg: any) => ({
      role: msg.role,
      content: msg.content,
      timestamp: msg.timestamp,
    }));
  } catch (error) {
    console.error('Error getting session messages:', error);
    return [];
  }
}

/**
 * Get conversations list from the backend
 */
export async function getConversations(): Promise<Convo[]> {
  try {
    const response = await fetch(API_ENDPOINTS.CONVERSATIONS, {
      method: 'GET',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      console.error('Failed to get conversations:', response.status, response.statusText);
      return [];
    }

    const data: RawConversation[] = await response.json();

    return data.map((conv: RawConversation) => ({
      id: conv.id,
      title: conv.title || "New Chat", // Fallback title if none exists
      created_at: new Date(conv.created_at),
    }));
  } catch (error) {
    console.error('Error getting conversations:', error);
    return [];
  }
}

/**
 * Endpoint management utilities
 */

/**
 * Get the stored API endpoint from localStorage
 */
export function getStoredEndpoint(): string {
  if (typeof window === 'undefined') return API_ENDPOINTS.CHAT_DEFAULT;
  return localStorage.getItem(ENDPOINT_STORAGE_KEY) || API_ENDPOINTS.CHAT_DEFAULT;
}

/**
 * Store the API endpoint in localStorage
 */
export function setStoredEndpoint(endpoint: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(ENDPOINT_STORAGE_KEY, endpoint);
}

/**
 * Clear the stored API endpoint from localStorage
 */
export function clearStoredEndpoint(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(ENDPOINT_STORAGE_KEY);
}
