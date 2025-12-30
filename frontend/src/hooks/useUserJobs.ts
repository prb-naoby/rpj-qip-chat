import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '@/lib/api';

export interface JobState {
    id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    result?: any;
    error?: string;
    user_id: string;
    user_username?: string;
    user_email?: string;
    job_type: string;
    submitted_at: string;
    started_at?: string;
    completed_at?: string;
    queue_position?: number;
    queue_total?: number;
    metadata?: {
        selectedFile?: { id: string; name: string; path: string };
        selectedSheet?: string;
        displayName?: string;
        previewTableId?: string;
    };
}

interface UseUserJobsOptions {
    jobType?: string;
    pollInterval?: number;
    backgroundPollInterval?: number;
}

export function useUserJobs(options: UseUserJobsOptions = {}) {
    const [jobs, setJobs] = useState<JobState[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const intervalRef = useRef<NodeJS.Timeout | null>(null);
    const backgroundIntervalRef = useRef<NodeJS.Timeout | null>(null);

    const {
        jobType,
        pollInterval = 1000,           // Fast polling when active (1 second)
        backgroundPollInterval = 5000   // Slower background polling (5 seconds)
    } = options;

    const fetchJobs = useCallback(async () => {
        try {
            const res = await api.getJobs(jobType);
            setJobs(prevJobs => {
                // Check for status changes to enable animations
                const newJobs = res.data;
                return newJobs;
            });
            return res.data;
        } catch (error) {
            console.error("Failed to fetch jobs:", error);
            return [];
        } finally {
            setIsLoading(false);
        }
    }, [jobType]);

    // Computed properties
    const activeJobs = jobs.filter(j => j.status === 'pending' || j.status === 'running');
    const latestJob = jobs.length > 0 ? jobs[0] : null;

    // Smart polling: fast when active jobs, slower otherwise
    useEffect(() => {
        const startPolling = (hasActive: boolean) => {
            // Clear existing intervals
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
            }
            if (backgroundIntervalRef.current) {
                clearInterval(backgroundIntervalRef.current);
                backgroundIntervalRef.current = null;
            }

            if (hasActive) {
                // Fast polling for active jobs
                intervalRef.current = setInterval(fetchJobs, pollInterval);
            } else {
                // Slower background polling for new jobs
                backgroundIntervalRef.current = setInterval(fetchJobs, backgroundPollInterval);
            }
        };

        // Single initial fetch and setup polling based on result
        const initPolling = async () => {
            const currentJobs = await fetchJobs();
            const hasActive = currentJobs.some((j: JobState) => j.status === 'pending' || j.status === 'running');
            startPolling(hasActive);
        };

        initPolling();

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
            if (backgroundIntervalRef.current) {
                clearInterval(backgroundIntervalRef.current);
            }
        };
    }, [fetchJobs, pollInterval, backgroundPollInterval]);

    // Force refresh helper
    const refresh = useCallback(() => {
        return fetchJobs();
    }, [fetchJobs]);

    return {
        jobs,
        activeJobs,
        latestJob,
        isLoading,
        refresh
    };
}
