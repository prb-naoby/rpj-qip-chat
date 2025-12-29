import { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'sonner';

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface JobState {
    id: string;
    status: JobStatus;
    result?: any;
    error?: string;
    submitted_at?: string;
    started_at?: string;
    completed_at?: string;
}

interface UseJobPollerOptions {
    onComplete?: (data: any) => void;
    onError?: (error: string) => void;
    persistenceKey?: string; // If provided, saves jobId to localStorage
}

export function useJobPoller(options: UseJobPollerOptions = {}) {
    const [job, setJob] = useState<JobState | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const intervalRef = useRef<NodeJS.Timeout | null>(null);

    // Load from specific persistence key on mount
    useEffect(() => {
        if (options.persistenceKey) {
            const savedJobId = localStorage.getItem(options.persistenceKey);
            if (savedJobId) {
                // Determine if we should clear it if it's old (optional, skipping for MVP)
                startPolling(savedJobId);
            }
        }
    }, [options.persistenceKey]);

    const poll = useCallback(async (jobId: string) => {
        try {
            const response = await fetch(`/api/jobs/${jobId}`);
            if (!response.ok) {
                if (response.status === 404) {
                    // Job lost (server restart?)
                    clearInterval(intervalRef.current!);
                    setJob(prev => prev ? { ...prev, status: 'failed', error: 'Job not found (server may have restarted)' } : null);
                    setIsLoading(false);
                    if (options.persistenceKey) localStorage.removeItem(options.persistenceKey);
                    return;
                }
                throw new Error('Failed to fetch job status');
            }

            const data: JobState = await response.json();
            setJob(data);

            if (data.status === 'completed') {
                clearInterval(intervalRef.current!);
                setIsLoading(false);
                if (options.persistenceKey) localStorage.removeItem(options.persistenceKey);
                options.onComplete?.(data.result);
                toast.success("Task completed successfully");
            } else if (data.status === 'failed') {
                clearInterval(intervalRef.current!);
                setIsLoading(false);
                if (options.persistenceKey) localStorage.removeItem(options.persistenceKey);
                options.onError?.(data.error || 'Unknown error');
                toast.error(`Task failed: ${data.error}`);
            }
        } catch (error) {
            console.error('Polling error:', error);
            // Don't stop polling on network error, likely transient
        }
    }, [options]);

    const startPolling = useCallback((jobId: string) => {
        setJob({ id: jobId, status: 'pending' });
        setIsLoading(true);

        if (options.persistenceKey) {
            localStorage.setItem(options.persistenceKey, jobId);
        }

        // Immediate check
        poll(jobId);

        // Clear existing interval
        if (intervalRef.current) clearInterval(intervalRef.current);

        // Poll every 1s
        intervalRef.current = setInterval(() => poll(jobId), 1000);
    }, [poll, options.persistenceKey]);

    const reset = useCallback(() => {
        if (intervalRef.current) clearInterval(intervalRef.current);
        setJob(null);
        setIsLoading(false);
        if (options.persistenceKey) localStorage.removeItem(options.persistenceKey);
    }, [options.persistenceKey]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, []);

    return {
        job,
        isLoading,
        startPolling,
        reset
    };
}
