"use client";
import { PlusCircleIcon } from '@heroicons/react/24/outline'
import { PlusCircle } from 'lucide-react';

import Starter from "@/components/starter";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
} from "@/components/ui/navigation-menu";

import { AIInput } from "@/components/ui/ai-input";
import { ModeToggle } from "@/components/ui/mode-toggle";
import DynamicLogo from "@/components/ui/dynamic-logo";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen relative">
      <NavigationMenu className="w-full max-w-[95vw] mx-auto flex justify-between items-center fixed top-4 left-1/2 -translate-x-1/2 z-10 shadow-md shadow-blue-400/20 border border-primary/5 rounded-2xl bg-background/85 backdrop-blur-sm">
        <div className="flex flex-row items-center p-4 space-x-2">
          <DynamicLogo width={30} height={30} />
          <h2 className="font-inter text-xl lg:text-3xl font-bold">ChatDKU</h2>
        </div>
        <NavigationMenuList>
          <NavigationMenuItem>
            <NavigationMenuLink href="/about" className="lg:text-md">
              About
            </NavigationMenuLink>
          </NavigationMenuItem>
          <NavigationMenuItem>
            <NavigationMenuLink href="/" className="lg:text-md flex flex-row items-center">
              New Chat
              <PlusCircle className='size-4 text-primary-500' />
            </NavigationMenuLink>
          </NavigationMenuItem>
          <NavigationMenuItem className="mr-2 lg:ml-4">
            <ModeToggle />
          </NavigationMenuItem>
        </NavigationMenuList>
      </NavigationMenu>

      <div className="flex flex-col items-center justify-center flex-grow">
        <Starter />
        <div
          id="chat-log"
          className="space-y-4 p-4 rounded-md h-[300px] overflow-y-auto"
        ></div>
      </div>
      <div className="w-full max-w-[95vw] fixed bottom-0 left-1/2 -translate-x-1/2 p-4 bg-background/50 backdrop-blur-sm border-t ">
        <div>
          <AIInput
            onSubmit={(value) => {
              if (!value.trim()) return;

              const chatLog = document.getElementById("chat-log");
              const messageElement = document.createElement("div");
              messageElement.className = "message user-message";
              messageElement.innerHTML = `<span>${value}</span>`;
              chatLog?.appendChild(messageElement);
              chatLog?.scrollTo(0, chatLog.scrollHeight);

              const loader = document.createElement("div");
              const loadingTxt = document.createElement("span");
              loadingTxt.innerHTML =
                "Searching relevant documents for you, this can take several seconds...";
              loader.className = "loader";
              const botMessageElement = document.createElement("div");
              botMessageElement.className = "message bot-message";
              botMessageElement.appendChild(loadingTxt);
              botMessageElement.appendChild(loader);
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
                  botResponse.className = "message bot-message";
                  botResponse.innerHTML = `<span>${data}</span>`;
                  chatLog?.appendChild(botResponse);
                  chatLog?.scrollTo(0, chatLog.scrollHeight);
                })
                .catch((error) => {
                  const errorMessage = document.createElement("div");
                  errorMessage.className = "message bot-message";
                  errorMessage.innerHTML = `<span>Error: ${error.message}</span>`;
                  chatLog?.appendChild(errorMessage);
                  chatLog?.scrollTo(0, chatLog.scrollHeight);
                });
            }}
          />
        </div>
        <p className="text-center text-xs text-muted-foreground">
          Developed by DKU Edge Intelligence Lab.
        </p>
      </div>
    </div>
  );
}
