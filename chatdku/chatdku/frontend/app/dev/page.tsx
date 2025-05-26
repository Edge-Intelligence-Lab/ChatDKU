"use client";
import { useState, useCallback, useEffect } from "react";
import { marked } from "marked";
import { useRouter } from 'next/navigation';
import Cookies from 'js-cookie';

import Starter from "@/components/starter";
import { AIInput } from "@/components/ui/ai-input";
import { Navbar } from "@/components/navbar";
import { PromptRecs } from "@/components/prompt_recs";

// Configure marked options
const configureMarked = () => {
  // Use only the options that are supported by the current MarkedOptions type
  marked.setOptions({
    breaks: true, // Enable line breaks
    gfm: true,    // Enable GitHub Flavored Markdown
  });
};

// Helper function to safely handle marked.parse which might return Promise<string>
const parseMarkdown = (content: string): string => {
  const parsed = marked.parse(content);
  // If it's a promise, return empty string initially (will be updated later)
  if (parsed instanceof Promise) {
    return '';
  }
  return parsed;
};

// Simulates a streaming effect for text
const streamText = async (text: string, elementContainer: HTMLElement, delay = 15) => {
  let currentText = '';
  const streamContainer = document.createElement('div');
  streamContainer.className = 'text-foreground whitespace-pre-wrap break-words overflow-wrap-anywhere markdown-content text-[0.9375rem]';
  elementContainer.appendChild(streamContainer);
  
  // Create cursor element
  const cursor = document.createElement('span');
  cursor.className = 'typing-cursor';
  cursor.innerHTML = '▌';
  cursor.style.animation = 'cursor-blink 1s infinite';
  streamContainer.appendChild(cursor);
  
  // Add styles for cursor if not already present
  if (!document.getElementById('cursor-style')) {
    const style = document.createElement('style');
    style.id = 'cursor-style';
    style.innerHTML = `
      @keyframes cursor-blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0; }
      }
      .typing-cursor {
        display: inline-block;
        margin-left: 1px;
      }
    `;
    document.head.appendChild(style);
  }
  
  // Split into tokens - in a real implementation you might want to use a more sophisticated approach
  const tokens = text.split(/(?<=[\s.,;:!?])/);
  
  for (const token of tokens) {
    currentText += token;
    streamContainer.textContent = currentText;
    streamContainer.appendChild(cursor);
    await new Promise(resolve => setTimeout(resolve, delay));
  }
  
  // Remove cursor when done
  cursor.remove();
  
  // Parse Markdown after streaming is complete
  streamContainer.innerHTML = parseMarkdown(text);
  
  return streamContainer;
};

// API endpoint
const API_ENDPOINT = "https://chatdku.dukekunshan.edu.cn/dev/chat";

export default function Home() {
  const [showStarter, setShowStarter] = useState(true);
  const [isChatboxCentered, setIsChatboxCentered] = useState(true);
  const [chatHistoryId, setChatHistoryId] = useState("");
  const [thinkingMode, setThinkingMode] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [apiEndpoint, setApiEndpoint] = useState("https://chatdku.dukekunshan.edu.cn/dev/chat");
  const router = useRouter();

  // Initialize marked configuration on component mount and check for terms acceptance
  useEffect(() => {
    configureMarked();
    
    // Check if the user has accepted terms and conditions
    const termsAccepted = Cookies.get('terms_accepted');
    if (!termsAccepted) {
      router.push('/landing');
    }
  }, [router]);

  const generateUniqueId = () => {
    return Date.now() + "-" + Math.random().toString(36).substring(2, 15);
  };

  const toggleThinkingMode = () => {
    setThinkingMode((prev) => !prev);
  };

  const handleFeedback = useCallback(
    async (userInput: any, answer: any, reason: any) => {
      try {
        // Change to use a local API route instead of direct backend call
        await fetch("/api/feedback", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            userInput,
            botAnswer: answer,
            feedbackReason: reason,
            chatHistoryId,
          }),
        });
      } catch (error) {
        console.error("Failed to save feedback:", error);
      }
    },
    [chatHistoryId]
  );

  const addMessageToChat = useCallback(
    (role: string, content: any, className: any, shouldStream = false) => {
      const chatLog = document.getElementById("chat-log");
      const messageElement = document.createElement("div");
      const isUser = role === "user";
      messageElement.className = `flex ${isUser ? "justify-end" : ""} w-full`;

      // For user messages or non-streamed assistant messages
      if (isUser || !shouldStream) {
        // Use DOMPurify to sanitize HTML content when it's from markdown
        const sanitizedContent = 
          role === "user" ? content : parseMarkdown(content);

        messageElement.innerHTML = `
        <div class="flex flex-col ${isUser ? "items-end max-w-[85%] sm:max-w-[80%]" : "items-start w-full sm:max-w-[85%]"}">
          <div class="flex flex-col ${isUser ? "lg:flex-row-reverse" : "lg:flex-row"} gap-3 px-4 py-2 ${className} rounded-3xl w-full overflow-hidden">
            ${
              isUser
                ? ""
                : '<div class="flex-shrink-0"><div class="w-8 h-8 rounded-full bg-transparent flex items-center justify-center"><img src="/logos/new_logo.svg" class="block dark:hidden p-1.5" alt="Logo"/><img src="/logos/new_logo.svg" class="hidden dark:block p-1.5" alt="Logo"/></div></div>'
            }
            <div class="${isUser ? "text-right" : "text-left"} overflow-hidden">
              <div class="text-foreground whitespace-pre-wrap break-words overflow-wrap-anywhere markdown-content ${!isUser ? 'text-[0.9375rem]' : ''}">${sanitizedContent}</div>
            </div>
          </div>
        </div>
      `;
        chatLog?.appendChild(messageElement);
        chatLog?.scrollTo(0, chatLog.scrollHeight);
        return messageElement.querySelector(".flex.flex-col"); // Return the inner container for feedback
      } 
      // For streamed assistant messages
      else {
        messageElement.innerHTML = `
        <div class="flex flex-col items-start w-full sm:max-w-[85%]">
          <div class="flex flex-col lg:flex-row gap-3 px-4 py-2 ${className} rounded-3xl w-full overflow-hidden">
            <div class="flex-shrink-0"><div class="w-8 h-8 rounded-full bg-transparent flex items-center justify-center"><img src="/logos/new_logo.svg" class="block dark:hidden p-1.5" alt="Logo"/><img src="/logos/new_logo.svg" class="hidden dark:block p-1.5" alt="Logo"/></div></div>
            <div class="text-left overflow-hidden" id="stream-container">
              <!-- Content will be streamed here -->
            </div>
          </div>
        </div>
      `;
        chatLog?.appendChild(messageElement);
        chatLog?.scrollTo(0, chatLog.scrollHeight);
        
        // Start streaming the content
        const streamContainer = messageElement.querySelector("#stream-container") as HTMLElement;
        if (streamContainer) {
          streamText(content, streamContainer);
        }
        
        return messageElement.querySelector(".flex.flex-col");
      }
    },
    []
  );

  return (
    <div className="flex flex-col min-h-screen relative selection:bg-zinc-800 selection:text-white dark:selection:bg-white dark:selection:text-black">
      <header className="sticky top-0 z-20 w-full">
        <Navbar />
      </header>

      <main className="flex-1 w-full flex flex-col items-center pt-16">
        <div
          id="chat-log"
          className="w-full max-w-3xl mx-auto space-y-4 p-4 pb-32 overflow-y-auto"
        ></div>
      </main>

      <div
        className={`w-full max-w-[95vw] p-2 pt-0 transition-all duration-300 ${
          isChatboxCentered
            ? "absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
            : "fixed bottom-0 left-1/2 -translate-x-1/2 bg-background/80 backdrop-blur-sm z-10"
        }`}
      >
        {showStarter && (
          <div className="w-full flex justify-center">
            <Starter />
          </div>
        )}
        <div>
          <AIInput
            thinkingMode={thinkingMode}
            onThinkingModeChange={(value) => setThinkingMode(value)}
            onInputChange={(value) => setInputValue(value)}
            onEndpointChange={setApiEndpoint}
            onSubmit={async (value) => {
              if (!value.trim()) return;

              setShowStarter(false);
              setIsChatboxCentered(false);

              const newChatHistoryId = generateUniqueId();
              setChatHistoryId(newChatHistoryId);

              addMessageToChat(
                "user",
                value,
                "bg-muted/50 dark:bg-muted/50 text-sm" // Removed background color classes
              );

              const botMessage = addMessageToChat(
                "assistant",
                "Searching relevant documents for you, please wait...",
                "text-sm"
              );

              try {
                const response = await fetch(apiEndpoint, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    messages: [{ role: "user", content: value }],
                    chatHistoryId: newChatHistoryId,
                    mode: thinkingMode ? "agent" : ""
                  }),
                });

                if (!response.ok) throw new Error("Failed to fetch response");
                
                if (botMessage) {
                  botMessage.remove();
                }

                // Create a message container for the streamed response
                const messageDiv = addMessageToChat(
                  "assistant",
                  "",
                  "text-sm",
                  true // Use streaming mode
                );

                // Get the stream container
                const streamContainer = messageDiv?.querySelector("#stream-container");
                if (!streamContainer) throw new Error("Failed to create stream container");

                // Process the streamed response
                const data = await response.text();
                
                // Instead of displaying all at once, simulate token-by-token streaming
                await streamText(data, streamContainer as HTMLElement);
                
                // Add feedback buttons after streaming is complete
                if (messageDiv) {
                  const feedbackDiv = document.createElement("div");
                  feedbackDiv.className = "ml-4 mb-2";
                  const feedbackContent = `
                    <div class="flex items-center gap-2 text-left">
                      <span class="text-sm text-muted-foreground">Was this response helpful?</span>
                      <button class="feedback-yes px-2 py-1 text-sm rounded-md bg-secondary/50 hover:bg-secondary">Yes</button>
                      <button class="feedback-no px-2 py-1 text-sm rounded-md bg-secondary/50 transition-all duration-300 hover:bg-red-600 hover:text-white">No</button>
                    </div>
                  `;
                  feedbackDiv.innerHTML = feedbackContent;

                  // Add event listeners to feedback buttons
                  const yesButton = feedbackDiv.querySelector(".feedback-yes");
                  const noButton = feedbackDiv.querySelector(".feedback-no");

                  yesButton?.addEventListener("click", () => {
                    handleFeedback(value, data, "helpful");
                    feedbackDiv.innerHTML =
                      '<span class="text-sm text-muted-foreground">Thanks for your feedback!</span>';
                  });

                  noButton?.addEventListener("click", () => {
                    feedbackDiv.innerHTML = `
                      <div class="fixed inset-0 bg-background/80 backdrop-blur-sm z-50">
                        <div class="fixed inset-0 flex items-center justify-center">
                          <div class="dialog bg-background border shadow-lg rounded-lg w-[90%] max-w-md p-6">
                            <h3 class="text-lg font-semibold mb-4">Sorry to hear that. Can you tell us why?</h3>
                            
                            <div class="feedback-options space-y-2" id="reason-options">
                              <button class="reason-btn w-full text-left px-3 py-2 rounded-md border hover:bg-accent text-foreground" data-reason="not_correct">Not Correct</button>
                              <button class="reason-btn w-full text-left px-3 py-2 rounded-md border hover:bg-accent text-foreground" data-reason="not_clear">Not Clear</button>
                              <button class="reason-btn w-full text-left px-3 py-2 rounded-md border hover:bg-accent text-foreground" data-reason="not_relevant">Not Relevant</button>
                              <button class="reason-btn w-full text-left px-3 py-2 rounded-md border hover:bg-accent text-foreground" data-reason="other">Other</button>
                            </div>
                
                            <textarea id="custom-reason" class="w-full mt-4 p-2 rounded-md border bg-background text-foreground hidden" rows="5" placeholder="Please describe the issue"></textarea>
                    
                            <div class="flex justify-end mt-6 space-x-2">
                              <button id="submit-feedback" class="btn px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90">Submit</button>
                              <button id="cancel-feedback" class="btn px-4 py-2 text-sm rounded-md bg-secondary text-secondary-foreground hover:bg-destructive hover:text-destructive-foreground">Cancel</button>
                            </div>
                          </div>
                        </div>
                      </div>
                    `;

                    const optionButtons =
                      feedbackDiv.querySelectorAll(".reason-btn");
                    const customReason = feedbackDiv.querySelector(
                      "#custom-reason"
                    ) as HTMLTextAreaElement;
                    const submitBtn =
                      feedbackDiv.querySelector("#submit-feedback");
                    const cancelBtn =
                      feedbackDiv.querySelector("#cancel-feedback");

                    let selectedReason: string | null = null;

                    optionButtons.forEach((btn) => {
                      btn.addEventListener("click", () => {
                        selectedReason =
                          (btn as HTMLElement).dataset.reason || null;

                        optionButtons.forEach((b) =>
                          b.classList.remove("bg-secondary", "text-white")
                        );
                        btn.classList.add("bg-secondary", "text-black");

                        if (selectedReason === "other") {
                          customReason.classList.remove("hidden");
                        } else {
                          customReason.classList.add("hidden");
                        }
                      });
                    });

                    submitBtn?.addEventListener("click", () => {
                      if (!selectedReason) return;

                      let reasonToSend =
                        selectedReason === "other"
                          ? customReason.value.trim()
                          : selectedReason;

                      if (selectedReason === "other" && !reasonToSend) {
                        customReason.classList.add("border-destructive");
                        customReason.placeholder = "Please write something!";
                        return;
                      }

                      handleFeedback(value, data, reasonToSend);
                      feedbackDiv.innerHTML = `<span class="text-sm text-muted-foreground">Thanks for your feedback!</span>`;
                    });

                    cancelBtn?.addEventListener("click", () => {
                      feedbackDiv.innerHTML = `<span class="text-sm text-muted-foreground">Feedback canceled.</span>`;
                    });
                  });

                  messageDiv.appendChild(feedbackDiv);
                }
              } catch (error) {
                if (botMessage) {
                  botMessage.remove();
                }
                addMessageToChat(
                  "assistant",
                  `Error: ${
                    error instanceof Error
                      ? error.message
                      : "An unknown error occurred"
                  }`,
                  "bg-destructive/10 dark:bg-destructive/20"
                );
              }
            }}
          />
          {isChatboxCentered && (
            <div 
              className={`transition-all duration-300 ${
                inputValue ? "opacity-0 max-h-0 overflow-hidden" : "opacity-100 max-h-96"
              }`}
            >
              <PromptRecs
                onPromptSelect={(prompt) => {
                  const aiInput = document.getElementById(
                    "ai-input"
                  ) as HTMLTextAreaElement;
                  if (aiInput) {
                    aiInput.value = prompt;
                    // Update the internal state of AIInput
                    const inputEvent = new Event("input", { bubbles: true });
                    aiInput.dispatchEvent(inputEvent);
                    // Trigger the onSubmit directly
                    const enterEvent = new KeyboardEvent("keydown", {
                      key: "Enter",
                      code: "Enter",
                      bubbles: true,
                      cancelable: true,
                      shiftKey: false,
                    });
                    aiInput.dispatchEvent(enterEvent);
                  }
                }}
              />
            </div>
          )}
        </div>
        {!isChatboxCentered && (
          <p className="text-center text-[11px]/3 py-0 text-muted-foreground/70">
            AI responses may contain errors. Please verify with your advisor/and or Academic Services if anything is unclear.
          </p>
        )}
      </div>
    </div>
  );
}
