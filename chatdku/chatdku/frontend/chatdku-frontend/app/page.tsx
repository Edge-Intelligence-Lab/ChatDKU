"use client";
import { useState, useCallback } from "react";
import { marked } from "marked";

import Starter from "@/components/starter";
import { AIInput } from "@/components/ui/ai-input";
import { Navbar } from "@/components/ui/navbar";

export default function Home() {
  const [showStarter, setShowStarter] = useState(true);
  const [isChatboxCentered, setIsChatboxCentered] = useState(true);
  const [chatHistory, setChatHistory] = useState([]);
  const [chatHistoryId, setChatHistoryId] = useState("");

  const generateUniqueId = () => {
    return Date.now() + '-' + Math.random().toString(36).substring(2, 15);
  };

  const handleFeedback = useCallback(async (userInput: any, answer: any, reason: any) => {
    try {
      await fetch('http://10.200.14.82:9016/save-feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          userInput,
          botAnswer: answer,
          feedbackReason: reason,
          chatHistoryId,
        })
      });
    } catch (error) {
      console.error('Failed to save feedback:', error);
    }
  }, [chatHistoryId]);

  const addMessageToChat = useCallback((role: string, content: any, className: any) => {
    const chatLog = document.getElementById("chat-log");
    const messageElement = document.createElement("div");
    messageElement.className = `flex items-center gap-3 p-4 rounded-lg ${className}`;
    
    const isUser = role === "user";
    messageElement.innerHTML = `
      <div class="flex-shrink-0">
        <div class="w-8 h-8 rounded-full ${isUser ? 'bg-white dark:bg-black' : 'bg-primary/20 dark:bg-primary/30'} flex items-center justify-center">
          ${isUser ? '<span class="text-sm font-medium">👤</span>' : '<img src="/logos/Light-Logo.png" class="block dark:hidden p-1.5" alt="Logo"/><img src="/logos/Dark-Logo.png" class="hidden dark:block p-1.5" alt="Logo"/>'}
        </div>
      </div>
      <div class="flex-1">
        <div class="text-sm text-foreground whitespace-pre-wrap">${content}</div>
      </div>
    `;
    
    chatLog?.appendChild(messageElement);
    chatLog?.scrollTo(0, chatLog.scrollHeight);
    return messageElement;
  }, []);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen relative">
      <Navbar />

      <div className="flex flex-col items-center justify-center flex-grow w-full">
        <div
          id="chat-log"
          className="w-full max-w-3xl mx-auto space-y-4 p-4 rounded-md h-[calc(100vh-200px)] overflow-y-auto"
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
              
              addMessageToChat("user", value, "bg-primary/5 dark:bg-primary/10");
              
              const botMessage = addMessageToChat(
                "assistant", 
                "Searching relevant documents for you, this can take several seconds...",
                "bg-muted/50 dark:bg-muted/30"
              );

              try {
                const response = await fetch("http://10.200.14.82:9015/chat", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    messages: [{role: "user", content: value}],
                    chatHistoryId: newChatHistoryId
                  }),
                });

                if (!response.ok) throw new Error("Failed to fetch response");

                const data = await response.text();
                botMessage.remove();
                addMessageToChat("assistant", marked.parse(data), "bg-muted/50 dark:bg-muted/30");
                
                // Add feedback buttons
                const feedbackDiv = document.createElement("div");
                feedbackDiv.className = "flex items-center gap-2 mt-2";
                feedbackDiv.innerHTML = `
                  <span class="text-sm text-muted-foreground">Was this response helpful?</span>
                  <button class="px-2 py-1 text-sm rounded-md bg-primary/10 hover:bg-primary/20">Yes</button>
                  <button class="px-2 py-1 text-sm rounded-md bg-destructive/10 hover:bg-destructive/20">No</button>
                `;
                botMessage.appendChild(feedbackDiv);

              } catch (error) {
                botMessage.remove();
                addMessageToChat(
                  "assistant",
                  `Error: ${error instanceof Error ? error.message : "An unknown error occurred"}`,
                  "bg-destructive/10 dark:bg-destructive/20"
                );
              }
            }}
          />
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
