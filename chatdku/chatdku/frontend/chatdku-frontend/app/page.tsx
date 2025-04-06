"use client";

import Starter from "@/components/starter";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
} from "@/components/ui/navigation-menu";

import Image from "next/image";
import { AIInput } from "@/components/ui/ai-input";
import { ModeToggle } from "@/components/ui/mode-toggle";

export default function Home() {
  return (
    <div className="p-4 flex">
      <NavigationMenu className="m-4 p-4 flex justify-between items-center absolute min-w-4/5 top-0 left-1/2 transform -translate-x-1/2 z-10 shadow-md shadow-blue-400/20 border border-primary/5 rounded-2xl">
        <div className="flex items-center p-2 space-x-2">
          <Image
        src={"/logos/Light-Logo.svg"}
        alt="ChatDKU Logo Light Variant"
        width={30}
        height={30}
          />
          <h2 className="font-inter text-3xl font-bold">ChatDKU</h2>
        </div>
        <NavigationMenuList>
          <NavigationMenuItem>
        <NavigationMenuLink href="/about" className="text-md">
          About
        </NavigationMenuLink>
          </NavigationMenuItem>
          <NavigationMenuItem>
        <NavigationMenuLink href="/" className="text-md">
          New session
        </NavigationMenuLink>
          </NavigationMenuItem>
          <NavigationMenuItem>
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
      <div className="space-y-8 min-w-[400px] absolute bottom-0 left-0 right-0 p-4">
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
        <p className="space-y-8 min-w-[400px] absolute bottom-0 left-0 right-0 p-1 text-sm text-muted-foreground">
          Developed by DKU Edge Intelligence Lab.
        </p>
      </div>
    </div>
  );
}
