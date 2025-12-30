'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Spinner } from '@/components/ui/spinner';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from '@/components/ui/dropdown-menu';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { CheckCircle, XCircle, Clock, PlayCircle, ChevronDown, Eye, FileText, Trash2, MoreVertical } from 'lucide-react';
import { JobState } from '@/hooks/useUserJobs';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { useAppSelector } from '@/store/hooks';

interface JobStatusListProps {
    jobs: JobState[];
    isLoading: boolean;
    title?: string;
    className?: string;
    typeFilter?: string[];
    onJobClick?: (job: JobState) => void;
    onJobsChange?: () => void;
    collapsible?: boolean;
    defaultCollapsed?: boolean;
    maxJobs?: number; // Limit number of displayed jobs
    compact?: boolean; // Hide edit/delete actions and show smaller UI
}

// Animation variants
const itemVariants = {
    hidden: { opacity: 0, y: -10 },
    show: { opacity: 1, y: 0, transition: { duration: 0.2 } },
    exit: { opacity: 0, x: 20, transition: { duration: 0.15 } }
};

export function JobStatusList({
    jobs,
    isLoading,
    title = "Background Jobs",
    className,
    typeFilter,
    onJobClick,
    onJobsChange,
    collapsible = true,
    defaultCollapsed = false,
    maxJobs,
    compact = false
}: JobStatusListProps) {
    const [isOpen, setIsOpen] = useState(!defaultCollapsed);
    const [deletingJobs, setDeletingJobs] = useState<Set<string>>(new Set());
    const [selectedFilter, setSelectedFilter] = useState<'all' | 'analyze' | 'transform'>('all');

    // Get current user ID for ownership check
    const currentUserId = useAppSelector((state) => state.auth.user?.id);

    // Confirmation dialog state
    const [deleteConfirm, setDeleteConfirm] = useState<{ type: 'single' | 'bulk'; jobId?: string; period?: string; displayName?: string } | null>(null);

    // Filter jobs by typeFilter prop or local filter
    const filteredJobs = typeFilter
        ? jobs.filter(job => typeFilter.includes(job.job_type))
        : selectedFilter === 'all'
            ? jobs
            : jobs.filter(job => job.job_type === selectedFilter);

    // Apply max limit and sort by newest first
    const displayJobs = maxJobs
        ? filteredJobs.slice(0, maxJobs)
        : filteredJobs;

    const confirmDeleteJob = (jobId: string, displayName: string, e?: React.MouseEvent) => {
        e?.stopPropagation();
        setDeleteConfirm({ type: 'single', jobId, displayName });
    };

    const confirmClearJobs = (period: 'hour' | 'today' | '3days' | 'all') => {
        const periodLabels = { hour: 'last hour', today: 'today', '3days': 'last 3 days', all: 'all jobs' };
        setDeleteConfirm({ type: 'bulk', period, displayName: periodLabels[period] });
    };

    const handleDeleteJob = async (jobId: string) => {
        setDeletingJobs(prev => new Set(prev).add(jobId));
        try {
            await api.deleteJob(jobId);
            toast.success('Job deleted');
            onJobsChange?.();
        } catch (error: any) {
            toast.error(`Failed to delete job: ${error.message}`);
        } finally {
            setDeletingJobs(prev => {
                const next = new Set(prev);
                next.delete(jobId);
                return next;
            });
        }
    };

    const handleClearJobs = async (period: 'hour' | 'today' | '3days' | 'all') => {
        try {
            await api.clearJobs(period);
            toast.success(`Jobs cleared (${period})`);
            onJobsChange?.();
        } catch (error: any) {
            toast.error(`Failed to clear jobs: ${error.message}`);
        }
    };

    if (isLoading && displayJobs.length === 0) {
        return (
            <div className="flex items-center gap-2 text-sm text-muted-foreground p-2">
                <Spinner className="w-4 h-4" />
                <span>Loading jobs...</span>
            </div>
        );
    }

    if (displayJobs.length === 0) {
        return null;
    }

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'completed': return <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />;
            case 'failed': return <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />;
            case 'running': return <Spinner className="w-4 h-4 text-blue-500 flex-shrink-0" />;
            default: return <Clock className="w-4 h-4 text-muted-foreground flex-shrink-0" />;
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'completed': return 'bg-green-500/10 text-green-600';
            case 'failed': return 'bg-red-500/10 text-red-600';
            case 'running': return 'bg-blue-500/10 text-blue-600';
            default: return 'bg-gray-100 text-gray-600';
        }
    };

    // User-friendly job type labels
    const JOB_TYPE_LABELS: Record<string, string> = {
        'analysis': 'Data Analysis',
        'transform': 'Transformation',
        'onedrive_upload': 'Upload to OneDrive',
        'ingest': 'Document Ingestion',
        'ingest_dry_run': 'Ingestion Test',
    };

    const getDisplayName = (job: JobState) => {
        if (job.metadata?.displayName) {
            return job.metadata.displayName;
        }
        return JOB_TYPE_LABELS[job.job_type] || job.job_type.replace(/_/g, ' ');
    };

    const activeCount = displayJobs.filter(j => j.status === 'running' || j.status === 'pending').length;

    const jobListContent = (
        <CardContent className="p-0">
            {/* Filter Tabs - only show if no typeFilter prop */}
            {!typeFilter && (
                <div className="flex items-center gap-1 p-2 border-b bg-muted/20">
                    <Button
                        variant={selectedFilter === 'all' ? 'default' : 'ghost'}
                        size="sm"
                        onClick={() => setSelectedFilter('all')}
                        className="h-6 px-2 text-[10px]"
                    >
                        All ({jobs.length})
                    </Button>
                    <Button
                        variant={selectedFilter === 'analysis' ? 'default' : 'ghost'}
                        size="sm"
                        onClick={() => setSelectedFilter('analysis')}
                        className="h-6 px-2 text-[10px]"
                    >
                        Analysis ({jobs.filter(j => j.job_type === 'analysis').length})
                    </Button>
                    <Button
                        variant={selectedFilter === 'transform' ? 'default' : 'ghost'}
                        size="sm"
                        onClick={() => setSelectedFilter('transform')}
                        className="h-6 px-2 text-[10px]"
                    >
                        Transform ({jobs.filter(j => j.job_type === 'transform').length})
                    </Button>
                </div>
            )}
            <ScrollArea className={compact ? "max-h-[150px]" : "max-h-[350px]"}>
                <AnimatePresence mode="popLayout">
                    {displayJobs.map((job) => (
                        <motion.div
                            key={job.id}
                            layout
                            variants={itemVariants}
                            initial="hidden"
                            animate="show"
                            exit="exit"
                            className={cn(
                                "flex gap-3 p-3 border-b border-border/30 last:border-0 transition-colors",
                                onJobClick && job.status === 'completed' && currentUserId !== undefined && String(job.user_id) === String(currentUserId) && "cursor-pointer hover:bg-muted/30",
                                deletingJobs.has(job.id) && "opacity-50"
                            )}
                            onClick={() => {
                                // Only allow owner to click and continue
                                if (onJobClick && job.status === 'completed' && currentUserId !== undefined && String(job.user_id) === String(currentUserId)) {
                                    onJobClick(job);
                                }
                            }}
                        >
                            <div className="flex-shrink-0 pt-0.5">
                                {getStatusIcon(job.status)}
                            </div>
                            <div className="flex-1 min-w-0 space-y-1">
                                {/* Header row */}
                                <div className="flex items-start justify-between gap-2">
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <FileText className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                                        <span className="text-sm font-medium break-words" title={getDisplayName(job)}>
                                            {getDisplayName(job)}
                                        </span>
                                        <Badge variant="outline" className="text-[9px] h-4 px-1 leading-none rounded-sm flex-shrink-0">
                                            {JOB_TYPE_LABELS[job.job_type] || job.job_type}
                                        </Badge>
                                    </div>
                                    {/* Actions - hidden in compact mode */}
                                    {!compact && (
                                        <div className="flex items-center gap-1 flex-shrink-0">
                                            {onJobClick && job.status === 'completed' && (
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="h-6 px-2 text-[10px] text-primary disabled:opacity-30 disabled:cursor-not-allowed"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        onJobClick(job);
                                                    }}
                                                    disabled={currentUserId !== undefined && String(job.user_id) !== String(currentUserId)}
                                                    title={String(job.user_id) !== String(currentUserId) ? "You can only continue your own jobs" : "View and apply results"}
                                                >
                                                    <Eye className="w-3 h-3 mr-1" />
                                                    View
                                                </Button>
                                            )}
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-6 w-6 p-0 text-muted-foreground hover:text-red-500 disabled:opacity-30 disabled:cursor-not-allowed"
                                                onClick={(e) => confirmDeleteJob(job.id, getDisplayName(job), e)}
                                                disabled={deletingJobs.has(job.id) || (currentUserId !== undefined && String(job.user_id) !== String(currentUserId))}
                                                title={String(job.user_id) !== String(currentUserId) ? "You can only delete your own jobs" : "Delete job"}
                                            >
                                                {deletingJobs.has(job.id) ? (
                                                    <Spinner className="w-3 h-3" />
                                                ) : (
                                                    <Trash2 className="w-3 h-3" />
                                                )}
                                            </Button>
                                        </div>
                                    )}
                                </div>
                                {/* Status row */}
                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="text-[10px] text-muted-foreground">
                                        {job.submitted_at && formatDistanceToNow(new Date(job.submitted_at), { addSuffix: true })}
                                    </span>
                                    <Badge variant="secondary" className={cn("text-[10px] h-4 px-1 leading-none rounded-sm", getStatusColor(job.status))}>
                                        {job.status}
                                    </Badge>
                                    {job.status === 'pending' && job.queue_position && (
                                        <Badge variant="outline" className="text-[10px] h-4 px-1 leading-none rounded-sm bg-yellow-500/10 text-yellow-600 border-yellow-200">
                                            Queue #{job.queue_position}
                                        </Badge>
                                    )}
                                    {/* Owner badge */}
                                    {job.user_username && (
                                        <Badge variant="outline" className="text-[10px] h-4 px-1.5 leading-none rounded-sm bg-muted/50">
                                            <span className="text-muted-foreground">by:</span> {job.user_username}
                                        </Badge>
                                    )}
                                </div>
                                {/* Error/Summary - now wrapping instead of truncating */}
                                {job.error && (
                                    <p className="text-[10px] text-red-500 break-words whitespace-pre-wrap">
                                        Error: {job.error}
                                    </p>
                                )}
                                {job.status === 'completed' && job.result?.summary && (
                                    <p className="text-[10px] text-green-600 break-words whitespace-pre-wrap">
                                        {job.result.summary}
                                    </p>
                                )}
                            </div>
                        </motion.div>
                    ))}
                </AnimatePresence>
            </ScrollArea>
        </CardContent>
    );

    const headerContent = (
        <div className="flex items-center justify-between w-full">
            <span className="flex items-center gap-2">
                <motion.div
                    animate={{ rotate: isOpen ? 0 : -90 }}
                    transition={{ duration: 0.2 }}
                >
                    <ChevronDown className="w-4 h-4" />
                </motion.div>
                <PlayCircle className={cn("w-4 h-4", activeCount > 0 ? "text-blue-500" : "text-primary")} />
                {title}
            </span>
            <div className="flex items-center gap-2">
                <Badge
                    variant="outline"
                    className={cn(
                        "text-[10px] font-normal",
                        activeCount > 0 && "bg-blue-500/10 text-blue-600 border-blue-200"
                    )}
                >
                    {activeCount > 0 ? `${activeCount} active` : `${displayJobs.length} jobs`}
                </Badge>
                {/* Clear jobs dropdown - hidden in compact mode */}
                {!compact && (
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                            <Button variant="ghost" size="sm" className="h-6 w-6 p-0 hover:bg-muted">
                                <MoreVertical className="w-3 h-3" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-48">
                            <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                                Clear History
                            </div>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                                onClick={(e) => { e.stopPropagation(); confirmClearJobs('hour'); }}
                                className="gap-2"
                            >
                                <Clock className="w-4 h-4 text-muted-foreground" />
                                <span>Last hour</span>
                            </DropdownMenuItem>
                            <DropdownMenuItem
                                onClick={(e) => { e.stopPropagation(); confirmClearJobs('today'); }}
                                className="gap-2"
                            >
                                <Clock className="w-4 h-4 text-muted-foreground" />
                                <span>Today</span>
                            </DropdownMenuItem>
                            <DropdownMenuItem
                                onClick={(e) => { e.stopPropagation(); confirmClearJobs('3days'); }}
                                className="gap-2"
                            >
                                <Clock className="w-4 h-4 text-muted-foreground" />
                                <span>Last 3 days</span>
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                                onClick={(e) => { e.stopPropagation(); confirmClearJobs('all'); }}
                                className="gap-2 text-red-600 focus:text-red-600 focus:bg-red-50"
                            >
                                <Trash2 className="w-4 h-4" />
                                <span>Clear all jobs</span>
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                )}
            </div>
        </div>
    );

    if (collapsible) {
        return (
            <>
                <Card className={cn("border-border/50 overflow-hidden", className)}>
                    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
                        <CollapsibleTrigger asChild>
                            <CardHeader className="py-3 px-4 cursor-pointer hover:bg-muted/30 transition-colors">
                                <CardTitle className="text-sm font-medium">
                                    {headerContent}
                                </CardTitle>
                            </CardHeader>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                            {jobListContent}
                        </CollapsibleContent>
                    </Collapsible>
                </Card>
                {/* Delete Confirmation Dialog */}
                <AlertDialog open={!!deleteConfirm} onOpenChange={(open) => !open && setDeleteConfirm(null)}>
                    <AlertDialogContent>
                        <AlertDialogHeader>
                            <AlertDialogTitle>
                                {deleteConfirm?.type === 'single' ? 'Delete Job?' : 'Clear Jobs?'}
                            </AlertDialogTitle>
                            <AlertDialogDescription>
                                {deleteConfirm?.type === 'single'
                                    ? `Are you sure you want to delete "${deleteConfirm?.displayName}"? This action cannot be undone.`
                                    : `Are you sure you want to clear jobs from ${deleteConfirm?.displayName}? This action cannot be undone.`
                                }
                            </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                                className="bg-red-600 hover:bg-red-700"
                                onClick={() => {
                                    if (deleteConfirm?.type === 'single' && deleteConfirm.jobId) {
                                        handleDeleteJob(deleteConfirm.jobId);
                                    } else if (deleteConfirm?.type === 'bulk' && deleteConfirm.period) {
                                        handleClearJobs(deleteConfirm.period as any);
                                    }
                                    setDeleteConfirm(null);
                                }}
                            >
                                Delete
                            </AlertDialogAction>
                        </AlertDialogFooter>
                    </AlertDialogContent>
                </AlertDialog>
            </>
        );
    }

    return (
        <>
            <Card className={cn("border-border/50", className)}>
                <CardHeader className="py-3 px-4">
                    <CardTitle className="text-sm font-medium">
                        {headerContent}
                    </CardTitle>
                </CardHeader>
                {jobListContent}
            </Card>
            {/* Delete Confirmation Dialog */}
            <AlertDialog open={!!deleteConfirm} onOpenChange={(open) => !open && setDeleteConfirm(null)}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>
                            {deleteConfirm?.type === 'single' ? 'Delete Job?' : 'Clear Jobs?'}
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                            {deleteConfirm?.type === 'single'
                                ? `Are you sure you want to delete "${deleteConfirm.displayName}"? This action cannot be undone.`
                                : `Are you sure you want to clear jobs from ${deleteConfirm?.displayName}? This action cannot be undone.`
                            }
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            className="bg-red-600 hover:bg-red-700"
                            onClick={() => {
                                if (deleteConfirm?.type === 'single' && deleteConfirm.jobId) {
                                    handleDeleteJob(deleteConfirm.jobId);
                                } else if (deleteConfirm?.type === 'bulk' && deleteConfirm.period) {
                                    handleClearJobs(deleteConfirm.period as any);
                                }
                                setDeleteConfirm(null);
                            }}
                        >
                            Delete
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    );
}
