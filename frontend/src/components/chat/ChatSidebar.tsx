import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { PlusCircle, MessageSquare, Trash2 } from "lucide-react";
import { ChatSession } from "@/store/slices/chatSlice";
import { format, isToday, isYesterday, subDays, isAfter } from "date-fns";

interface ChatSidebarProps {
    sessions: ChatSession[];
    currentSessionId: string | null;
    onSelectSession: (id: string) => void;
    onNewChat: () => void;
    onDeleteSession?: (id: string) => void;
    className?: string;
}

export function ChatSidebar({
    sessions,
    currentSessionId,
    onSelectSession,
    onNewChat,
    onDeleteSession,
    className
}: ChatSidebarProps) {

    // Group sessions by date
    const groupedSessions = sessions.reduce((groups, session) => {
        const date = new Date(session.updated_at);
        let key = 'Older';

        if (isToday(date)) {
            key = 'Today';
        } else if (isYesterday(date)) {
            key = 'Yesterday';
        } else if (isAfter(date, subDays(new Date(), 7))) {
            key = 'Previous 7 Days';
        }

        if (!groups[key]) groups[key] = [];
        groups[key].push(session);
        return groups;
    }, {} as Record<string, ChatSession[]>);

    const groups = ['Today', 'Yesterday', 'Previous 7 Days', 'Older'];

    return (
        <div className={cn("hidden md:flex w-[260px] flex-col border-r bg-muted/10 h-full", className)}>
            <div className="p-4">
                <Button
                    onClick={onNewChat}
                    className="w-full justify-start gap-2 bg-background border shadow-sm hover:bg-accent text-foreground"
                    variant="outline"
                >
                    <PlusCircle className="h-4 w-4" />
                    New chat
                </Button>
            </div>

            <ScrollArea className="flex-1 px-4">
                <div className="space-y-6 pb-4">
                    {groups.map((group) => {
                        const groupSessions = groupedSessions[group];
                        if (!groupSessions || groupSessions.length === 0) return null;

                        return (
                            <div key={group} className="space-y-2">
                                <h4 className="text-xs font-semibold text-muted-foreground px-2">{group}</h4>
                                <div className="space-y-1">
                                    {groupSessions.map((session) => (
                                        <button
                                            key={session.id}
                                            onClick={() => onSelectSession(session.id)}
                                            className={cn(
                                                "w-full text-left px-3 py-2 text-sm rounded-md transition-colors flex items-center justify-between group",
                                                currentSessionId === session.id
                                                    ? "bg-accent/50 text-accent-foreground font-medium"
                                                    : "text-muted-foreground hover:bg-accent/30 hover:text-foreground"
                                            )}
                                        >
                                            <span className="truncate flex-1 pr-2">
                                                {session.title || "New Chat"}
                                            </span>
                                            {onDeleteSession && (
                                                <div
                                                    role="button"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        onDeleteSession(session.id);
                                                    }}
                                                    className="opacity-0 group-hover:opacity-100 p-1 hover:text-destructive transition-opacity"
                                                >
                                                    <Trash2 className="h-4 w-4" />
                                                </div>
                                            )}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        );
                    })}

                    {sessions.length === 0 && (
                        <div className="text-center text-xs text-muted-foreground mt-8 px-4">
                            No chat history
                        </div>
                    )}
                </div>
            </ScrollArea>
        </div>
    );
}
