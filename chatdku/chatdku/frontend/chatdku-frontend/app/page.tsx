"use client";
import { useState } from 'react';

import Starter from "@/components/starter";
import { AIInput } from "@/components/ui/ai-input";
import { Navbar } from "@/components/ui/navbar";

export default function Home() {
  const [showStarter, setShowStarter] = useState(true);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen relative">
      <Navbar />

      <div className="flex flex-col items-center justify-center flex-grow w-full">
        {showStarter && (
          <div className="w-full flex justify-center">
            <Starter />
          </div>
        )}
        <div
          id="chat-log"
          className="w-full max-w-3xl mx-auto space-y-4 p-4 rounded-md h-[calc(100vh-300px)] overflow-y-auto"
        ></div>
      </div>
      <div className="w-full max-w-[95vw] fixed bottom-0 left-1/2 -translate-x-1/2 p-4 pt-0 backdrop-blur-md">
        <div>
          <AIInput
            onSubmit={(value) => {
              if (!value.trim()) return;

              setShowStarter(false);

              const chatLog = document.getElementById("chat-log");
              const messageElement = document.createElement("div");
              messageElement.className = "flex items-start gap-3 p-4 rounded-lg bg-primary/5 dark:bg-primary/10";
              messageElement.innerHTML = `
                <div class="flex-shrink-0">
                  <div class="w-8 h-8 rounded-full bg-primary/20 dark:bg-primary/30 flex items-center justify-center">
                    <span class="text-sm font-medium">U</span>
                  </div>
                </div>
                <div class="flex-1">
                  <div class="text-sm text-foreground">${value}</div>
                </div>
              `;
              chatLog?.appendChild(messageElement);
              chatLog?.scrollTo(0, chatLog.scrollHeight);

              const loader = document.createElement("div");
              const loadingTxt = document.createElement("span");
              loadingTxt.innerHTML = "Searching relevant documents for you, this can take several seconds...";
              loader.className = "loader";
              const botMessageElement = document.createElement("div");
              botMessageElement.className = "flex items-start gap-3 p-4 rounded-lg bg-muted/50 dark:bg-muted/30";
              botMessageElement.innerHTML = `
                <div class="flex-shrink-0">
                  <div class="w-8 h-8 rounded-full bg-primary/20 dark:bg-primary/30 flex items-center justify-center overflow-hidden">
                    <DynamicLogo width={32} height={32} />
                  </div>
                </div>
                <div class="flex-1">
                  <div class="text-sm text-foreground">${loadingTxt.outerHTML}</div>
                  <div class="mt-2">${loader.outerHTML}</div>
                </div>
              `;
              chatLog?.appendChild(botMessageElement);
              chatLog?.scrollTo(0, chatLog.scrollHeight);

              fetch("http://10.200.14.82:9015/chat", {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                },
                body: JSON.stringify({
                  messages: [{ role: "user", content: value }],
                }),
              })
                .then((response) => {
                  loader.remove();
                  loadingTxt.remove();
                  if (response.ok) {
                    return response.text();
                  } else {
                    throw new Error("Failed to fetch response");
                  }
                })
                .then((data) => {
                  const botResponse = document.createElement("div");
                  botResponse.className = "flex items-start gap-3 p-4 rounded-lg bg-muted/50 dark:bg-muted/30";
                  botResponse.innerHTML = `
                    <div class="flex-shrink-0">
                      <div class="w-8 h-8 rounded-full bg-primary/20 dark:bg-primary/30 flex items-center justify-center overflow-hidden">
                        <DynamicLogo width={32} height={32} />
                      </div>
                    </div>
                    <div class="flex-1">
                      <div class="text-sm text-foreground whitespace-pre-wrap">${data}</div>
                    </div>
                  `;
                  chatLog?.appendChild(botResponse);
                  chatLog?.scrollTo(0, chatLog.scrollHeight);
                })
                .catch((error) => {
                  const errorMessage = document.createElement("div");
                  errorMessage.className = "flex items-start gap-3 p-4 rounded-lg bg-destructive/10 dark:bg-destructive/20";
                  errorMessage.innerHTML = `
                    <div class="flex-shrink-0">
                      <div class="w-8 h-8 rounded-full bg-destructive/20 dark:bg-destructive/30 flex items-center justify-center">
                        <span class="text-sm font-medium">!</span>
                      </div>
                    </div>
                    <div class="flex-1">
                      <div class="text-sm text-destructive">Error: ${error.message}</div>
                    </div>
                  `;
                  chatLog?.appendChild(errorMessage);
                  chatLog?.scrollTo(0, chatLog.scrollHeight);
                });
            }}
          />
        </div>
        <p className="text-center text-xs text-muted-foreground">
          AI responses may contain errors.
        </p>
      </div>
    </div>
  );
}
