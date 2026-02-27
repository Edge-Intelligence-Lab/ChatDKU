const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3005";
const dictationWsUrl =
  process.env.NEXT_PUBLIC_DICTATION_WS_URL || "ws://localhost:8007";

export const API_ENDPOINTS = {
    USER: `${apiBaseUrl}/user`,
    CHAT_DEFAULT: `${apiBaseUrl}/api/chat`,
    CHAT_DEV1: `${apiBaseUrl}/dev/ant/chat`,
    CHAT_DEV2: `${apiBaseUrl}/dev/qwen/chat`,
    CHAT_DEV3: `${apiBaseUrl}/dev/inp/chat`,
    CHAT_DEV4: `${apiBaseUrl}/dev/django/chat`,
    FILE_UPLOAD: `${apiBaseUrl}/user_files`,
    DICTATION_WS: dictationWsUrl,
    NEW_SESSION: `${apiBaseUrl}/api/get_session`,
    CONVERSATIONS: `${apiBaseUrl}/api/c/`,
    SESSION_MESSAGES: (sessionId: string) =>
      `${apiBaseUrl}/api/c/${sessionId}/messages`,
  } as const;
  
  export const CHAT_MODELS = [
    {
      id: "default",
      name: "Default",
      endpoint: API_ENDPOINTS.CHAT_DEFAULT,
    },
    { id: "ant", name: "Course Planning", endpoint: API_ENDPOINTS.CHAT_DEV1 },
    { id: "qwen", name: "Qwen", endpoint: API_ENDPOINTS.CHAT_DEV2 },
    { id: "inp", name: "Artemis", endpoint: API_ENDPOINTS.CHAT_DEV3 },
    { id: "django", name: "Django Testing", endpoint: API_ENDPOINTS.CHAT_DEV4 },
  ] as const;
  
  // TODO: Move all old sample questions here below:
  export const EXAMPLE_QUESTIONS = [
    { emoji: "🔬", question: "Explain quantum computing principles" },
    { emoji: "📚", question: "Summarize recent AI research papers" },
    { emoji: "💡", question: "Help me brainstorm research ideas" },
    { emoji: "📊", question: "Analyze this dataset for patterns" },
    { emoji: "🧮", question: "Solve complex mathematical problems" },
    { emoji: "🌍", question: "Discuss climate change impacts" },
  ] as const;
  
