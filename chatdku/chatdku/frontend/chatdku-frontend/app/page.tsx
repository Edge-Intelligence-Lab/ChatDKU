"use client";
import { useState, useCallback } from "react";
import { marked } from "marked";

import Starter from "@/components/starter";
import { AIInput } from "@/components/ui/ai-input";
import { Navbar } from "@/components/navbar";
import { PromptRecs } from "@/components/prompt_recs";

export default function Home() {
  const [showStarter, setShowStarter] = useState(true);
  const [isChatboxCentered, setIsChatboxCentered] = useState(true);
  const [chatHistory, setChatHistory] = useState([]);
  const [chatHistoryId, setChatHistoryId] = useState("");

  const generateUniqueId = () => {
    return Date.now() + "-" + Math.random().toString(36).substring(2, 15);
  };

  const handleFeedback = useCallback(
    async (userInput: any, answer: any, reason: any) => {
      try {
        await fetch("http://10.200.14.82:9016/save-feedback", {
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
    (role: string, content: any, className: any) => {
      const chatLog = document.getElementById("chat-log");
      const messageElement = document.createElement("div");
      const isUser = role === "user";
      messageElement.className = `flex ${isUser ? 'justify-end' : ''} w-full`;

      messageElement.innerHTML = `
      <div class="flex flex-col ${isUser ? 'items-end max-w-[85%] sm:max-w-[80%]' : 'items-start w-full sm:max-w-[85%]'}">
        <div class="flex flex-col ${isUser ? 'lg:flex-row-reverse' : 'lg:flex-row'} gap-3 px-4 py-2 ${className} rounded-3xl w-full overflow-hidden">
          ${isUser ? '' : '<div class="flex-shrink-0"><div class="w-8 h-8 rounded-full bg-white dark:bg-black flex items-center justify-center"><img src="/logos/new_logo.svg" class="block dark:hidden p-1.5" alt="Logo"/><img src="/logos/new_logo.svg" class="hidden dark:block p-1.5" alt="Logo"/></div></div>'}
          <div class="${isUser ? 'text-right' : 'text-left'} overflow-hidden">
            <div class="text-foreground whitespace-pre-wrap break-words overflow-wrap-anywhere">${content}</div>
          </div>
        </div>
      </div>
    `;
      chatLog?.appendChild(messageElement);
      chatLog?.scrollTo(0, chatLog.scrollHeight);
      return messageElement.querySelector('.flex.flex-col'); // Return the inner container for feedback
    },
    []
  );

  return (
    <div className="flex flex-col items-center justify-center min-h-screen relative">
      <Navbar />

      <div className="flex flex-col lg:justify-normal items-center flex-grow w-full">
        <div
          id="chat-log"
          className="w-full max-w-3xl mx-auto space-y-4 mt-12 lg:mt-0 p-4 lg:h-[calc(100vh-90px)] h-[calc(100vh-150px)] overflow-y-auto"
        ></div>
      </div>
      <div
        className={`w-full max-w-[95vw] p-2 pt-0 transition-all duration-300 ${
          isChatboxCentered
            ? "absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
            : "fixed bottom-0 left-1/2 -translate-x-1/2"
        }`}
      >
        {showStarter && (
          <div className="w-full flex justify-center">
            <Starter />
          </div>
        )}
        <div>
          <AIInput
            onSubmit={async (value) => {
              if (!value.trim()) return;

              setShowStarter(false);
              setIsChatboxCentered(false);

              const newChatHistoryId = generateUniqueId();
              setChatHistoryId(newChatHistoryId);

              addMessageToChat(
                "user",
                value,
                "bg-muted/50 dark:bg-muted/50 text-sm font-bold" // Removed background color classes
              );

              const botMessage = addMessageToChat(
                "assistant",
                "Searching relevant documents for you, please wait...",
                "text-sm"
              );

              try {
                const response = await fetch("http://10.200.14.82:8000/chat", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    messages: [{ role: "user", content: value }],
                    chatHistoryId: newChatHistoryId,
                  }),
                });

                if (!response.ok) throw new Error("Failed to fetch response");

                const data = await response.text();
                if (botMessage) {
                  botMessage.remove();
                }
                const messageDiv = addMessageToChat(
                  "assistant",
                  marked.parse(data),
                  "text-sm"
                );

                if (messageDiv) { // Add null check here
                  // Add feedback buttons
                  const feedbackDiv = document.createElement("div");
                  feedbackDiv.className = "mt-2 mb-2";
                  const feedbackContent = `
                    <div class="flex items-center gap-2 text-left">
                      <span class="text-sm text-muted-foreground">Was this response helpful?</span>
                      <button class="feedback-yes px-2 py-1 text-sm rounded-md bg-secondary/50 hover:bg-secondary">Yes</button>
                      <button class="feedback-no px-2 py-1 text-sm rounded-md bg-secondary/50 hover:bg-destructive/50">No</button>
                    </div>
                  `;
                  feedbackDiv.innerHTML = feedbackContent;

                  // Add event listeners to feedback buttons
                  const yesButton = feedbackDiv.querySelector('.feedback-yes');
                  const noButton = feedbackDiv.querySelector('.feedback-no');

                  yesButton?.addEventListener('click', () => {
                    handleFeedback(value, data, 'helpful');
                    feedbackDiv.innerHTML = '<span class="text-sm text-muted-foreground">Thanks for your feedback!</span>';
                  });

                  noButton?.addEventListener('click', () => {
                    handleFeedback(value, data, 'not_helpful');
                    feedbackDiv.innerHTML = '<span class="text-sm text-muted-foreground">Thanks for your feedback!</span>';
                  });

                  messageDiv.appendChild(feedbackDiv);
                }
              } catch (error) {
                if (botMessage) {
                  botMessage.remove();
                }
                addMessageToChat(
                  "assistant",
                  `Error: ${error instanceof Error ? error.message : "An unknown error occurred"}`,
                  "bg-destructive/10 dark:bg-destructive/20"
                );
              }
            }}
          />
          {isChatboxCentered && (
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
          )}
        </div>
        {!isChatboxCentered && (
          <p className="text-center text-[11px]/0 pb-1 text-muted-foreground/70">
            AI responses may contain errors.
          </p>
        )}
      </div>
    </div>
  );
}
