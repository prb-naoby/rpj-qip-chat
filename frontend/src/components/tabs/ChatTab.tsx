'use client';

/**
 * Chat Tab Component
 * Main chat interface for asking questions about data
 */
import { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
    addMessage,
    streamQuestion,
    fetchSessions,
    createSession,
    loadChatHistory,
    setCurrentSession
} from '@/store/slices/chatSlice';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';

import { AnalysisResult } from '@/components/chat/AnalysisResult';
import { Spinner } from '@/components/ui/spinner';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ChevronDown, User, Sparkles, ArrowUp } from 'lucide-react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';

import { RootState } from '@/store';

export default function ChatTab() {
    const dispatch = useAppDispatch();
    const { messages, isLoading, streamingStatus } = useAppSelector((state: RootState) => state.chat);
    const { tables } = useAppSelector((state: RootState) => state.tables);

    const [inputValue, setInputValue] = useState('');

    // Load sessions on mount
    useEffect(() => {
        dispatch(fetchSessions());
    }, [dispatch]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!inputValue.trim() || isLoading) return;

        const question = inputValue.trim();
        setInputValue('');

        if (tables.length === 0) {
            dispatch(addMessage({ role: 'user', content: question }));
            dispatch(addMessage({
                role: 'assistant',
                content: '⚠️ No tables found. Please upload a file or sync from OneDrive first.'
            }));
            return;
        }

        // Send question - let backend handle table selection automatically
        dispatch(addMessage({ role: 'user', content: question }));
        dispatch(streamQuestion({ question, tableId: '' }));
    };

    const handleAnalysisAction = (action: string, data: any) => {
        if (action === 'select_table') {
            const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
            if (lastUserMsg) {
                dispatch(streamQuestion({
                    question: lastUserMsg.content,
                    tableId: data.cache_path
                }));
            }
        }
    };

    return (
        <div className="flex flex-col h-[calc(100vh-100px)] md:h-[calc(100vh-140px)]">
            {/* Messages Area - takes remaining space */}
            <div className="flex-1 overflow-hidden relative">
                <ScrollArea className="h-full px-2 md:px-4 lg:px-6">
                    <div className="w-full max-w-full md:max-w-4xl lg:max-w-6xl mx-auto py-4 md:py-8 pb-4 space-y-4 md:space-y-6">
                        {messages.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-[60vh] text-center space-y-6">
                                <div className="bg-primary/5 p-6 rounded-full ring-1 ring-primary/10">
                                    <Sparkles className="h-12 w-12 text-primary" />
                                </div>
                                <div className="space-y-2 max-w-md">
                                    <h3 className="text-2xl font-semibold tracking-tight">QIP Analytics Assistant</h3>
                                    <p className="text-muted-foreground text-lg">
                                        Ask any question about your data.
                                    </p>
                                </div>
                            </div>
                        ) : (
                            <AnimatePresence mode="popLayout">
                                {messages.map((msg: any) => (
                                    <motion.div
                                        key={msg.id}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, scale: 0.95 }}
                                        transition={{ duration: 0.2 }}
                                        className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
                                    >
                                        {/* Avatar */}
                                        <Avatar className={`h-8 w-8 mt-1 flex-shrink-0 border ${msg.role === 'user' ? 'bg-primary border-primary' : 'bg-muted border-border'}`}>
                                            <AvatarFallback className={msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'}>
                                                {msg.role === 'user' ? <User className="h-4 w-4" /> : <Sparkles className="h-4 w-4 text-primary" />}
                                            </AvatarFallback>
                                        </Avatar>

                                        {/* Message Content - stretch for assistant, constrained for user */}
                                        <div className={`flex flex-col ${msg.role === 'user' ? 'max-w-[85%] sm:max-w-[75%] items-end' : 'w-full max-w-3xl items-start'}`}>
                                            {msg.role === 'user' ? (
                                                /* User message - simple bubble */
                                                <div className="px-4 py-3 rounded-2xl shadow-sm text-sm leading-relaxed bg-primary text-primary-foreground rounded-tr-sm">
                                                    <div className="whitespace-pre-wrap">{msg.content}</div>
                                                </div>
                                            ) : (
                                                /* Assistant message - unified card with text + UI components, stretches wide */
                                                <div className="bg-card border border-border/50 rounded-2xl rounded-tl-sm shadow-sm overflow-hidden w-full">
                                                    {/* Text content */}
                                                    {msg.content && (
                                                        <div className="px-4 py-3 text-sm leading-relaxed text-foreground">
                                                            <div className="whitespace-pre-wrap">{msg.content}</div>
                                                        </div>
                                                    )}

                                                    {/* UI Components inside the card */}
                                                    {msg.ui_components && msg.ui_components.length > 0 && (
                                                        <div className="px-4 pb-4">
                                                            <AnalysisResult
                                                                components={msg.ui_components}
                                                                onAction={handleAnalysisAction}
                                                            />
                                                        </div>
                                                    )}

                                                    {/* Methodology section - show explanation instead of code */}
                                                    {(msg.explanation || msg.code) && (
                                                        <div className="px-4 pb-3 border-t border-border/30">
                                                            <Collapsible className="w-full">
                                                                <CollapsibleTrigger className="flex items-center gap-2 text-xs font-medium text-muted-foreground hover:text-primary transition-colors py-2">
                                                                    <ChevronDown className="h-3 w-3" />
                                                                    <span>View Methodology</span>
                                                                </CollapsibleTrigger>
                                                                <CollapsibleContent>
                                                                    <div className="p-3 bg-muted/50 rounded-lg border border-border/50">
                                                                        <p className="text-sm text-foreground/80 whitespace-pre-wrap leading-relaxed">
                                                                            {msg.explanation || "Hasil diperoleh dari analisis langsung terhadap data yang tersedia."}
                                                                        </p>
                                                                    </div>
                                                                </CollapsibleContent>
                                                            </Collapsible>
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    </motion.div>
                                ))}
                            </AnimatePresence>
                        )}

                        {isLoading && (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="flex gap-3"
                            >
                                <Avatar className="h-8 w-8 mt-1 bg-muted border border-border flex-shrink-0">
                                    <AvatarFallback className="bg-muted">
                                        <Sparkles className="h-4 w-4 text-primary" />
                                    </AvatarFallback>
                                </Avatar>
                                <div className="flex items-center gap-2 text-muted-foreground text-sm py-2">
                                    <div className="h-2 w-2 bg-primary rounded-full animate-bounce [animation-delay:-0.3s]" />
                                    <div className="h-2 w-2 bg-primary rounded-full animate-bounce [animation-delay:-0.15s]" />
                                    <div className="h-2 w-2 bg-primary rounded-full animate-bounce" />
                                    <span className="ml-2 font-medium">{streamingStatus || "Thinking..."}</span>
                                </div>
                            </motion.div>
                        )}
                    </div>
                </ScrollArea>
            </div>

            {/* Input Area - Fixed at bottom */}
            <div className="flex-shrink-0 p-4 bg-gradient-to-t from-background via-background to-transparent border-t border-border/30">
                <div className="w-full max-w-full md:max-w-4xl lg:max-w-6xl mx-auto relative">
                    <form onSubmit={handleSubmit} className="relative flex shadow-lg rounded-full bg-background ring-1 ring-border focus-within:ring-2 focus-within:ring-primary/20 transition-all">
                        <Input
                            placeholder="Ask follow-up..."
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            className="flex-1 border-0 focus-visible:ring-0 bg-transparent py-4 md:py-6 pl-4 md:pl-6 pr-12 md:pr-14 text-base shadow-none rounded-full"
                            disabled={isLoading}
                            aria-label="Type your question"
                        />
                        <div className="absolute right-2 top-1.5">
                            <Button
                                type="submit"
                                size="icon"
                                disabled={isLoading || !inputValue.trim()}
                                aria-label="Send message"
                                className={`rounded-full h-9 w-9 transition-all ${!inputValue.trim() ? 'opacity-0 scale-75' : 'opacity-100 scale-100'}`}
                            >
                                {isLoading ? <Spinner className="h-4 w-4" /> : <ArrowUp className="h-4 w-4" />}
                            </Button>
                        </div>
                    </form>
                    <p className="text-center text-[10px] text-muted-foreground mt-2 opacity-50">
                        AI can make mistakes. Please verify important information.
                    </p>
                </div>
            </div>
        </div>
    );
}
