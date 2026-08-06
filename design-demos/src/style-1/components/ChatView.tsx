import { useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { mockMessages, type ConversationMessage } from "@/lib/mock-data";
import { Sidebar } from "./Sidebar";
import { BrandLogo } from "./BrandLogo";
import { ConversationThread } from "./ConversationThread";
import { ChatComposer } from "./ChatComposer";

interface ChatViewProps {
  activeConversationId: string | null;
  onSelectConversation?: (id: string) => void;
  onNewChat?: () => void;
  onNewProject?: () => void;
  onSelectProject?: (id: string) => void;
}

export function ChatView({
  activeConversationId,
  onSelectConversation,
  onNewChat,
  onNewProject,
  onSelectProject,
}: ChatViewProps) {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [webEnabled, setWebEnabled] = useState(false);

  useEffect(() => {
    if (activeConversationId) {
      setMessages(mockMessages);
    } else {
      setMessages([]);
    }
    setIsThinking(false);
  }, [activeConversationId]);

  const handleSend = (text?: string) => {
    const content = (text ?? input).trim();
    if (!content) return;
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: "user", content },
    ]);
    setInput("");
    setIsThinking(true);
    window.setTimeout(() => {
      setIsThinking(false);
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          content:
            "Based on the sources in your library, here are the key points worth examining. Would you like me to expand on any of them with specific citations?",
        },
      ]);
    }, 1800);
  };

  const sidebarProps = {
    activeConversationId,
    onSelectConversation,
    onNewChat,
    onNewProject,
    onSelectProject,
  };

  return (
    <Sheet>
      <div className="grid h-[100dvh] bg-gradient-to-br from-accent via-background to-background md:grid-cols-[260px_1fr]">
        {/* Desktop sidebar */}
        <aside className="hidden h-full md:block">
          <Sidebar {...sidebarProps} />
        </aside>

        {/* Main column */}
        <main className="flex h-full min-h-0 flex-col overflow-hidden">
          {/* Mobile top bar */}
          <div className="flex items-center gap-2 border-b border-border/40 bg-white/50 px-4 py-2.5 backdrop-blur-sm md:hidden">
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="h-9 w-9">
                <Menu className="h-5 w-5" strokeWidth={1.5} />
              </Button>
            </SheetTrigger>
            <BrandLogo />
          </div>

          {/* Conversation thread */}
          <div className="min-h-0 flex-1">
            <ConversationThread
              messages={messages}
              isThinking={isThinking}
              onSelectPrompt={(prompt) => handleSend(prompt)}
            />
          </div>

          {/* Glass composer */}
          <ChatComposer
            value={input}
            onChange={setInput}
            onSend={() => handleSend()}
            webEnabled={webEnabled}
            onToggleWeb={() => setWebEnabled((v) => !v)}
          />
        </main>
      </div>

      {/* Mobile sidebar */}
      <SheetContent side="left" className="w-[280px] p-0">
        <Sidebar {...sidebarProps} className="border-r-0" />
      </SheetContent>
    </Sheet>
  );
}
