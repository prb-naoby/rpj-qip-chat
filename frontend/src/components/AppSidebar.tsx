import { MessageCircle, Cloud, Upload, Settings, History, Star, Bot, Plus, ChevronRight, Settings2, MoreHorizontal, Pencil, Trash2, X } from 'lucide-react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchSessions, setCurrentSession, createSession, deleteSession, renameSession, loadChatHistory } from '@/store/slices/chatSlice';
import { useEffect, useState } from 'react';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Sidebar,
    SidebarContent,
    SidebarFooter,
    SidebarGroup,
    SidebarGroupContent,
    SidebarGroupLabel,
    SidebarHeader,
    SidebarMenu,
    SidebarMenuButton,
    SidebarMenuItem,
    SidebarMenuSub,
    SidebarMenuSubButton,
    SidebarMenuSubItem,
    SidebarSeparator,
    SidebarRail,
} from '@/components/ui/sidebar';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import ProfileCard from '@/components/ProfileCard';

type TabType = 'chat' | 'onedrive' | 'upload' | 'manage';

interface AppSidebarProps {
    activeTab: TabType;
    onTabChange: (tab: TabType) => void;
    onLogout: () => void;
}

export function AppSidebar({ activeTab, onTabChange, onLogout }: AppSidebarProps) {
    const dispatch = useAppDispatch();
    const { sessions, currentSessionId } = useAppSelector((state) => state.chat);

    useEffect(() => {
        dispatch(fetchSessions());
    }, [dispatch]);

    const handleNewChat = () => {
        dispatch(createSession("New Chat")).then((res: any) => {
            if (createSession.fulfilled.match(res)) {
                dispatch(setCurrentSession(res.payload.id));
                onTabChange('chat');
            }
        });
    };

    const handleLoadSession = (sessionId: string) => {
        dispatch(loadChatHistory(sessionId));
        onTabChange('chat');
    };

    // Rename & Delete State
    const [renameId, setRenameId] = useState<string | null>(null);
    const [renameTitle, setRenameTitle] = useState("");
    const [deleteId, setDeleteId] = useState<string | null>(null);
    const [showAllSessions, setShowAllSessions] = useState(false);

    const startRename = (id: string, currentTitle: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setRenameId(id);
        setRenameTitle(currentTitle);
    };

    const confirmRename = async () => {
        if (renameId && renameTitle.trim()) {
            await dispatch(renameSession({ chatId: renameId, title: renameTitle }));
            setRenameId(null);
        }
    };

    const startDelete = (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setDeleteId(id);
    };

    const confirmDelete = async () => {
        if (deleteId) {
            await dispatch(deleteSession(deleteId));
            setDeleteId(null);
        }
    };

    return (
        <Sidebar>
            <SidebarHeader className="p-4">
                <SidebarMenu>
                    <SidebarMenuItem>
                        <div className="flex items-center justify-between">
                            <h1 className="text-xl font-bold flex items-center gap-2">
                                <Bot className="size-6 text-primary" />
                                <span>QIP Analytics</span>
                            </h1>
                            <div className="ml-auto">
                                <ThemeToggle />
                            </div>
                        </div>
                    </SidebarMenuItem>
                </SidebarMenu>
            </SidebarHeader>

            <SidebarSeparator />

            <SidebarContent>
                {/* Workspace Group */}
                <SidebarGroup>
                    <SidebarGroupLabel>Workspace</SidebarGroupLabel>
                    <SidebarGroupContent>
                        <SidebarMenu>
                            {/* Workspace Collapsible */}
                            <Collapsible asChild defaultOpen className="group/collapsible">
                                <SidebarMenuItem>
                                    <CollapsibleTrigger asChild>
                                        <SidebarMenuButton tooltip="AI Workspace" isActive={activeTab === 'chat'}>
                                            <Bot className="size-4" />
                                            <span>AI Assistant</span>
                                            <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                                        </SidebarMenuButton>
                                    </CollapsibleTrigger>
                                    <CollapsibleContent>
                                        <SidebarMenuSub>
                                            {/* Action: New Session */}
                                            <SidebarMenuSubItem>
                                                <SidebarMenuSubButton onClick={handleNewChat}>
                                                    <Plus className="mr-2 size-4" />
                                                    <span>New Create</span>
                                                </SidebarMenuSubButton>
                                            </SidebarMenuSubItem>

                                            {/* Recent Sessions (History) */}
                                            <Collapsible asChild className="group/history">
                                                <SidebarMenuSubItem>
                                                    <CollapsibleTrigger asChild>
                                                        <SidebarMenuSubButton>
                                                            <History className="mr-2 size-4" />
                                                            <span>Recent Sessions</span>
                                                            <ChevronRight className="ml-auto size-3 transition-transform duration-200 group-data-[state=open]/history:rotate-90" />
                                                        </SidebarMenuSubButton>
                                                    </CollapsibleTrigger>
                                                    <CollapsibleContent>
                                                        <SidebarMenuSub>
                                                            <AnimatePresence>
                                                                {sessions.length === 0 ? (
                                                                    <motion.div
                                                                        initial={{ opacity: 0 }}
                                                                        animate={{ opacity: 1 }}
                                                                        exit={{ opacity: 0 }}
                                                                        className="px-4 py-2 text-xs text-muted-foreground italic"
                                                                    >
                                                                        No history yet
                                                                    </motion.div>
                                                                ) : (
                                                                    sessions.slice(0, 5).map(session => (
                                                                        <motion.div
                                                                            key={session.id}
                                                                            initial={{ opacity: 0, x: -10 }}
                                                                            animate={{ opacity: 1, x: 0 }}
                                                                            exit={{ opacity: 0, height: 0 }}
                                                                            transition={{ duration: 0.2 }}
                                                                        >
                                                                            <SidebarMenuSubItem className="relative group/item">
                                                                                <SidebarMenuSubButton
                                                                                    onClick={() => handleLoadSession(session.id)}
                                                                                    isActive={currentSessionId === session.id && activeTab === 'chat'}
                                                                                    className="cursor-pointer pr-8"
                                                                                >
                                                                                    <span className="truncate">{session.title}</span>
                                                                                </SidebarMenuSubButton>
                                                                                <div className="absolute right-1 top-1/2 -translate-y-1/2 opacity-0 group-hover/item:opacity-100 transition-opacity">
                                                                                    <DropdownMenu>
                                                                                        <DropdownMenuTrigger asChild>
                                                                                            <Button
                                                                                                variant="ghost"
                                                                                                size="icon"
                                                                                                className="h-6 w-6"
                                                                                                onClick={(e) => e.stopPropagation()}
                                                                                            >
                                                                                                <MoreHorizontal className="h-4 w-4" />
                                                                                            </Button>
                                                                                        </DropdownMenuTrigger>
                                                                                        <DropdownMenuContent align="end">
                                                                                            <DropdownMenuItem onClick={(e) => startRename(session.id, session.title, e)}>
                                                                                                <Pencil className="mr-2 h-4 w-4" />
                                                                                                Rename
                                                                                            </DropdownMenuItem>
                                                                                            <DropdownMenuItem
                                                                                                onClick={(e) => startDelete(session.id, e)}
                                                                                                className="text-destructive focus:text-destructive"
                                                                                            >
                                                                                                <Trash2 className="mr-2 h-4 w-4" />
                                                                                                Delete
                                                                                            </DropdownMenuItem>
                                                                                        </DropdownMenuContent>
                                                                                    </DropdownMenu>
                                                                                </div>
                                                                            </SidebarMenuSubItem>
                                                                        </motion.div>
                                                                    ))
                                                                )}
                                                            </AnimatePresence>
                                                            {sessions.length > 5 && !showAllSessions && (
                                                                <SidebarMenuSubItem>
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="sm"
                                                                        onClick={() => setShowAllSessions(true)}
                                                                        className="w-full justify-start text-xs text-primary hover:text-primary h-7 px-2"
                                                                    >
                                                                        + {sessions.length - 5} more...
                                                                    </Button>
                                                                </SidebarMenuSubItem>
                                                            )}
                                                            {showAllSessions && sessions.slice(5).map(session => (
                                                                <motion.div
                                                                    key={session.id}
                                                                    initial={{ opacity: 0, x: -10 }}
                                                                    animate={{ opacity: 1, x: 0 }}
                                                                    transition={{ duration: 0.2 }}
                                                                >
                                                                    <SidebarMenuSubItem className="relative group/item">
                                                                        <SidebarMenuSubButton
                                                                            onClick={() => handleLoadSession(session.id)}
                                                                            isActive={currentSessionId === session.id && activeTab === 'chat'}
                                                                            className="cursor-pointer pr-8"
                                                                        >
                                                                            <span className="truncate">{session.title}</span>
                                                                        </SidebarMenuSubButton>
                                                                        <div className="absolute right-1 top-1/2 -translate-y-1/2 opacity-0 group-hover/item:opacity-100 transition-opacity">
                                                                            <DropdownMenu>
                                                                                <DropdownMenuTrigger asChild>
                                                                                    <Button
                                                                                        variant="ghost"
                                                                                        size="icon"
                                                                                        className="h-6 w-6"
                                                                                        onClick={(e) => e.stopPropagation()}
                                                                                    >
                                                                                        <MoreHorizontal className="h-4 w-4" />
                                                                                    </Button>
                                                                                </DropdownMenuTrigger>
                                                                                <DropdownMenuContent align="end">
                                                                                    <DropdownMenuItem onClick={(e) => startRename(session.id, session.title, e)}>
                                                                                        <Pencil className="mr-2 h-4 w-4" />
                                                                                        Rename
                                                                                    </DropdownMenuItem>
                                                                                    <DropdownMenuItem
                                                                                        onClick={(e) => startDelete(session.id, e)}
                                                                                        className="text-destructive focus:text-destructive"
                                                                                    >
                                                                                        <Trash2 className="mr-2 h-4 w-4" />
                                                                                        Delete
                                                                                    </DropdownMenuItem>
                                                                                </DropdownMenuContent>
                                                                            </DropdownMenu>
                                                                        </div>
                                                                    </SidebarMenuSubItem>
                                                                </motion.div>
                                                            ))}
                                                            {showAllSessions && sessions.length > 5 && (
                                                                <SidebarMenuSubItem>
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="sm"
                                                                        onClick={() => setShowAllSessions(false)}
                                                                        className="w-full justify-start text-xs text-muted-foreground h-7 px-2"
                                                                    >
                                                                        Show less
                                                                    </Button>
                                                                </SidebarMenuSubItem>
                                                            )}
                                                        </SidebarMenuSub>
                                                    </CollapsibleContent>
                                                </SidebarMenuSubItem>
                                            </Collapsible>
                                        </SidebarMenuSub>
                                    </CollapsibleContent>
                                </SidebarMenuItem>
                            </Collapsible>
                        </SidebarMenu>
                    </SidebarGroupContent>
                </SidebarGroup>

                <SidebarSeparator />

                {/* Data Group */}
                <SidebarGroup>
                    <SidebarGroupLabel>Data Sources</SidebarGroupLabel>
                    <SidebarGroupContent>
                        <SidebarMenu>
                            <SidebarMenuItem>
                                <SidebarMenuButton onClick={() => onTabChange('onedrive')} isActive={activeTab === 'onedrive'} tooltip="Browse OneDrive">
                                    <Cloud className="size-4" />
                                    <span>OneDrive</span>
                                </SidebarMenuButton>
                            </SidebarMenuItem>
                            <SidebarMenuItem>
                                <SidebarMenuButton onClick={() => onTabChange('upload')} isActive={activeTab === 'upload'} tooltip="Upload Files">
                                    <Upload className="size-4" />
                                    <span>Upload</span>
                                </SidebarMenuButton>
                            </SidebarMenuItem>
                        </SidebarMenu>
                    </SidebarGroupContent>
                </SidebarGroup>

                <SidebarGroup>
                    <SidebarGroupLabel>Admin</SidebarGroupLabel>
                    <SidebarGroupContent>
                        <SidebarMenu>
                            <SidebarMenuItem>
                                <SidebarMenuButton onClick={() => onTabChange('manage')} isActive={activeTab === 'manage'} tooltip="Manage Tables">
                                    <Settings className="size-4" />
                                    <span>Manage</span>
                                </SidebarMenuButton>
                            </SidebarMenuItem>
                        </SidebarMenu>
                    </SidebarGroupContent>
                </SidebarGroup>

            </SidebarContent>

            <SidebarSeparator />

            <SidebarFooter>
                <div className="p-2">
                    <ProfileCard onLogout={onLogout} />
                </div>
            </SidebarFooter>

            {/* Rename Dialog */}
            <Dialog open={!!renameId} onOpenChange={(open) => !open && setRenameId(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Rename Session</DialogTitle>
                    </DialogHeader>
                    <div className="py-4">
                        <Input
                            value={renameTitle}
                            onChange={(e) => setRenameTitle(e.target.value)}
                            placeholder="Session Name"
                            onKeyDown={(e) => e.key === 'Enter' && confirmRename()}
                        />
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setRenameId(null)}>Cancel</Button>
                        <Button onClick={confirmRename}>Save</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete Alert */}
            <AlertDialog open={!!deleteId} onOpenChange={(open) => !open && setDeleteId(null)}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete Chat Session?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This action cannot be undone. This will permanently delete the chat history.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={confirmDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                            Delete
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </Sidebar>
    );
}

export type { TabType };
