import {
  ChevronRight,
  FileText,
  Menu,
  MessageCircle,
  MessageCircleQuestion,
  SquarePen,
} from "lucide-react";
import { Button } from "./ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import DynamicLogo from "./dynamic-logo";
import { ComboBoxResponsive } from "./ui/combobox";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ScrollArea } from "./ui/scroll-area";
import { useEffect, useState } from "react";

import { Convo, getConversations } from "@/lib/convosNew";

import { cn } from "@/components/utils";

interface SidebarProps {
  onDocumentManager: () => void;
  onEndpointChange?: (endpoint: string) => void;
  currentSessionId?: string;
  onNewChat: () => void;
  onConversationSelect: (sessionId: string) => void;

  currentEndpoint?: string;

}

export default function Side({
  onDocumentManager,
  onEndpointChange,
  currentSessionId,
  onNewChat,
  onConversationSelect,

  currentEndpoint,

}: SidebarProps) {
  const pathname = usePathname();
  const isDevRoute = pathname === "/dev" || pathname === "/dev/";
  const [conversations, setConversations] = useState<Convo[]>([]);

  useEffect(() => {
    const loadConversations = async () => {
      const convos = await getConversations();
      setConversations(convos);
    };
    loadConversations();
  }, []);

  return (
    <div className="fixed z-50">
      <Sheet>
        <SheetTrigger>
          <div className="m-2 p-2 hover:outline-1 cursor-pointer rounded-2xl active:bg-accent">
            <Menu className="" />
          </div>
        </SheetTrigger>
        <SheetContent side="left">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-x-1">
              <DynamicLogo width={35} height={35} />
              ChatDKU
            </SheetTitle>
          </SheetHeader>

          <div className="px-2 flex flex-col space-y-1.5 h-full">

            <Button
              variant="inChatbox"
              className="w-full justify-start"
              onClick={onNewChat}
            >
              <SquarePen />
              New Chat
            </Button>

            <div className={cn(!isDevRoute && "hidden")}>
              <Button
                variant="inChatbox"
                onClick={onDocumentManager}
                className="w-full justify-start"
              >
                <FileText />
                Document Manager
                <ChevronRight className="ml-auto" />
              </Button>
            </div>

            <Link href="/about">
              <Button variant="inChatbox" className="w-full justify-start">
                <MessageCircleQuestion />
                About ChatDKU
              </Button>
            </Link>

            <div className={cn(!isDevRoute && "hidden")}>
              <p className="ml-2 mt-4 text-sm text-muted-foreground">
                Model Selection
              </p>
              <ComboBoxResponsive
                inputValue={currentEndpoint || ""}
                onEndpointChange={onEndpointChange ?? (() => {})}
              />
            </div>
            <p className="ml-2 mt-4 text-sm text-muted-foreground">
              Chat History
            </p>
            <ScrollArea className="flex-1 min-h-0 px-4">

              <div className="space-y-1 pb-4">
                {conversations.length > 0 ? (
                  conversations.map((conversation) => (
                    <Button
                      key={conversation.id}
                      variant="ghost"
                      onClick={() => onConversationSelect(conversation.id)}
                      className={cn(
                        "w-full justify-start gap-3 text-left h-auto p-3 text-sidebar-foreground hover:bg-sidebar-accent",
                        currentSessionId === conversation.id &&
                          "bg-sidebar-accent",
                      )}
                    >
                      <MessageCircle className="h-4 w-4 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium truncate">
                          {conversation.title}
                        </div>
                        <div className="text-xs text-sidebar-foreground/60">
                          {conversation.created_at.toLocaleDateString()}
                        </div>
                      </div>
                    </Button>
                  ))
                ) : (
                  <div className="text-sm text-sidebar-foreground/60 text-center py-4">
                    No conversations yet
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
