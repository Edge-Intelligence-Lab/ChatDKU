export const API_ENDPOINTS = {
    USER: "https://chatdku.dukekunshan.edu.cn/user",
    CHAT_DEFAULT: "https://chatdku.dukekunshan.edu.cn/api/chat",
    CHAT_DEV1: "https://chatdku.dukekunshan.edu.cn/dev/ant/chat",
    CHAT_DEV2: "https://chatdku.dukekunshan.edu.cn/dev/qwen/chat",
    FILE_UPLOAD: "https://chatdku.dukekunshan.edu.cn/user_files",
    DICTATION_WS: "https://chatdku.dukekunshan.edu.cn:8007",
    NEW_SESSION: "https://chatdku.dukekunshan.edu.cn/api/get_session",
    CONVERSATIONS: "https://chatdku.dukekunshan.edu.cn/api/c/",
    SESSION_MESSAGES: (sessionId: string) =>
      `https://chatdku.dukekunshan.edu.cn/api/c/${sessionId}/messages`,
  } as const;
  
  export const CHAT_MODELS = [
    {
      id: "default",
      name: "Default Model",
      endpoint: API_ENDPOINTS.CHAT_DEFAULT,
    },
    { id: "ant", name: "Ant Model", endpoint: API_ENDPOINTS.CHAT_DEV1 },
    { id: "qwen", name: "Qwen Model", endpoint: API_ENDPOINTS.CHAT_DEV2 },
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
  