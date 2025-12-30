'use client';

/**
 * OneDrive Tab Component
 * Browse and import files from OneDrive with inline data transformation
 * 
 * FLOW:
 * 1. Refresh → Select file → Select sheet → Load
 * 2. Show preview + text input + (Analyze & Transform | Save As-Is)
 * 3. If analyze clicked → Show transformed preview + code + (Refine | Save)
 */
import { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchTables } from '@/store/slices/tablesSlice';
import { RootState } from '@/store';
import { api } from '@/lib/api';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Spinner } from '@/components/ui/spinner';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Label } from '@/components/ui/label';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { ChevronDown, CheckCircle, Wand2, Save, RefreshCw, Code, AlertTriangle, X } from 'lucide-react';

import { DataPreview } from '@/components/DataPreview';
import { useUserJobs } from '@/hooks/useUserJobs';
import { JobStatusList } from '@/components/JobStatusList';

import {
    setFiles,
    setSelectedFile,
    setSheets,
    setSelectedSheet,
    setPreviewTableId,
    setTransformInput,
    setAnalysisResult,
    setTransformedPreview,
    setSaveMode,
    setTargetTableId,
    setAppendDescription,
    setActiveJobId
} from '@/store/slices/oneDriveSlice';

interface OneDriveFile {
    id: string;
    name: string;
    path: string;
    size: number;
    downloadUrl: string;
    webUrl: string;
    lastModified: string;
}



interface OneDriveStatus {
    configured: boolean;
    error: string | null;
    root_path: string | null;
}

interface AnalysisResult {
    summary: string;
    issues_found: string[];
    transform_code: string;
    needs_transform: boolean;
    validation_notes: string[];
    explanation: string;
    preview_data: any[];
    has_error: boolean;
}

interface TransformPreview {
    columns: string[];
    preview_data: any[];
    error?: string;
}

export default function OneDriveTab() {
    const dispatch = useAppDispatch();

    // Job polling
    const { jobs, isLoading: isJobsLoading, refresh: refreshJobs } = useUserJobs();

    // Redux State
    const {
        files,
        filesLoaded,
        selectedFile,
        sheets,
        selectedSheet,
        previewTableId,
        transformInput,
        analysisResult,
        transformedPreview,
        saveMode,
        targetTableId,
        appendDescription
    } = useAppSelector((state: RootState) => state.oneDrive);

    // Local UI State (Transient)
    const [status, setStatus] = useState<OneDriveStatus | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isLoadingSheet, setIsLoadingSheet] = useState(false);
    const [isFetchingSheets, setIsFetchingSheets] = useState(false);

    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [feedbackInput, setFeedbackInput] = useState('');
    const [isRefining, setIsRefining] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [showSuccessAlert, setShowSuccessAlert] = useState(true);
    const [isCodeExpanded, setIsCodeExpanded] = useState(false);

    // Collapsible state
    const [isFileBrowserOpen, setIsFileBrowserOpen] = useState(true);
    const [isOriginalPreviewExpanded, setIsOriginalPreviewExpanded] = useState(true);
    const [isTransformedPreviewExpanded, setIsTransformedPreviewExpanded] = useState(true);

    const [isAppending, setIsAppending] = useState(false);
    const [appendError, setAppendError] = useState<string | null>(null);

    // Smart Append UI state
    interface AppendValidation {
        columns_match: boolean;
        compatible: boolean;
        issues: string[];
        target_has_transform: boolean;
        transform_explanation: string | null;
        similarity_reason: string | null;
        target_columns: string[];
        source_columns: string[];
    }
    interface AppendTransformPreview {
        success: boolean;
        preview_data: any[];
        preview_columns: string[];
        error?: string;
        generated_code?: string;
    }
    const [appendValidation, setAppendValidation] = useState<AppendValidation | null>(null);
    const [isValidating, setIsValidating] = useState(false);
    const [appendTransformPreview, setAppendTransformPreview] = useState<AppendTransformPreview | null>(null);
    const [isPreviewingTransform, setIsPreviewingTransform] = useState(false);
    const [transformFeedback, setTransformFeedback] = useState('');
    const [isConfirmingTransform, setIsConfirmingTransform] = useState(false);
    const [mappingDescription, setMappingDescription] = useState('');
    const [isGeneratingTransform, setIsGeneratingTransform] = useState(false);
    const [generatedTransformCode, setGeneratedTransformCode] = useState<string | null>(null);

    // Upload to OneDrive state


    // Get existing tables for append target selection
    const tables = useAppSelector((state: RootState) => state.tables.tables);

    useEffect(() => {
        checkStatus();
        dispatch(fetchTables());
    }, [dispatch]);

    useEffect(() => {
        // Reset validation when target table changes
        resetAppendState();
    }, [targetTableId]);

    const checkStatus = async () => {
        try {
            const response = await api.getOneDriveStatus();
            setStatus(response.data);
        } catch (error) {
            console.error('Failed to check OneDrive status:', error);
        }
    };



    const loadFiles = async () => {
        setIsLoading(true);
        try {
            // Load ALL files (no subfolder filter) - UI will group by folder
            const response = await api.listOneDriveFiles();
            dispatch(setFiles(response.data));
            toast.success(`✅ ${response.data.length} file ditemukan`);
        } catch (error: any) {
            toast.error(`Gagal memuat file: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsLoading(false);
        }
    };


    const handleFileClick = async (file: OneDriveFile) => {
        // Reset all states when new file selected
        dispatch(setSelectedFile(file));
        dispatch(setPreviewTableId(null));
        dispatch(setSheets([]));
        dispatch(setSelectedSheet(""));
        resetTransformState();
        setIsFileBrowserOpen(false);

        // Check if Excel
        const isExcel = file.name.match(/\.(xlsx|xls)$/i);
        if (isExcel) {
            setIsFetchingSheets(true);
            try {
                const response = await api.getOneDriveSheets(file.id, file.downloadUrl);
                const sheetList = response.data.sheets || [];
                dispatch(setSheets(sheetList));
                if (sheetList.length > 0) {
                    dispatch(setSelectedSheet(sheetList[0]));
                }
            } catch (error: any) {
                console.error("Failed to fetch sheets:", error);
                toast.error("Failed to fetch sheet list");
            } finally {
                setIsFetchingSheets(false);
            }
        }
    };

    const resetTransformState = () => {
        dispatch(setTransformInput(''));
        dispatch(setAnalysisResult(null));
        dispatch(setTransformedPreview(null));
        setFeedbackInput('');
    };

    const handleLoadSheet = async () => {
        if (!selectedFile) return;

        setIsLoadingSheet(true);
        resetTransformState();

        try {
            let displayName = selectedFile.name.replace(/\.(xlsx|xls|csv)$/i, '');
            if (selectedSheet) {
                displayName += ` - ${selectedSheet}`;
            }

            const response = await api.loadOneDriveSheet(
                selectedFile.id,
                selectedFile.downloadUrl,
                selectedFile.name,
                displayName,
                selectedSheet || undefined
            );

            toast.success(`✅ Sheet "${displayName}" loaded - ready to preview`);
            if (response.data.cache_path) {
                dispatch(setPreviewTableId(response.data.cache_path));
            }
            // Note: Don't dispatch(fetchTables()) here - table appears in Manage only after explicit save
        } catch (error: any) {
            toast.error(`Failed to load sheet: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsLoadingSheet(false);
        }
    };

    // Track the current analysis job ID
    const [analysisJobId, setAnalysisJobId] = useState<string | null>(null);

    // Effect: Watch for analysis job completion
    useEffect(() => {
        if (!analysisJobId) return;

        const job = jobs.find(j => j.id === analysisJobId);
        if (job) {
            if (job.status === 'completed') {
                if (job.result) {
                    dispatch(setAnalysisResult(job.result));

                    // Automatically preview if we have code
                    if (job.result.transform_code) {
                        // We can trigger preview here or let user click. 
                        // Let's auto-preview to match previous behavior (but carefully).
                        api.previewTransform(previewTableId!, job.result.transform_code)
                            .then(res => {
                                if (!res.data.error) {
                                    dispatch(setTransformedPreview({
                                        columns: res.data.columns,
                                        preview_data: res.data.preview_data
                                    }));
                                }
                            });
                    }

                    setIsOriginalPreviewExpanded(false);
                    toast.success(`✨ ${job.result.summary}`);
                    setAnalysisJobId(null); // Stop watching
                    setIsAnalyzing(false);
                }
            } else if (job.status === 'failed') {
                toast.error(`Analysis failed: ${job.error}`);
                setAnalysisJobId(null);
                setIsAnalyzing(false);
            }
        }
    }, [jobs, analysisJobId, previewTableId]);

    // Handle clicking on a completed job to restore state
    const handleJobClick = async (job: typeof jobs[0]) => {
        if (job.status === 'completed' && job.metadata) {
            // Restore file selection
            if (job.metadata.selectedFile) {
                dispatch(setSelectedFile(job.metadata.selectedFile as OneDriveFile));
            }
            if (job.metadata.selectedSheet) {
                dispatch(setSelectedSheet(job.metadata.selectedSheet));
            }
            if (job.metadata.previewTableId) {
                dispatch(setPreviewTableId(job.metadata.previewTableId));

                // Async fetch original data preview
                try {
                    await api.getTablePreview(job.metadata.previewTableId);
                    // The previewTableId being set will trigger DataPreview to load
                } catch (err) {
                    console.warn('Failed to load original preview:', err);
                }
            }
            // Restore analysis result
            if (job.result) {
                dispatch(setAnalysisResult({
                    summary: job.result.summary || '',
                    issues_found: job.result.issues_found || [],
                    transform_code: job.result.transform_code || '',
                    needs_transform: job.result.needs_transform || false,
                    validation_notes: job.result.validation_notes || [],
                    explanation: job.result.explanation || '',
                    preview_data: job.result.preview_data || [],
                    has_error: job.result.has_error || false
                }));

                // Restore transformed preview if available
                if (job.result.preview_data && job.result.preview_columns) {
                    dispatch(setTransformedPreview({
                        columns: job.result.preview_columns,
                        preview_data: job.result.preview_data
                    }));
                }
            }
            // Collapse file browser to show results
            setIsFileBrowserOpen(false);
            setIsOriginalPreviewExpanded(false);
            toast.success('State restored from completed job');
        }
    };

    // Auto-load completed job result
    const activeJobId = useAppSelector((state: RootState) => state.oneDrive.activeJobId);

    useEffect(() => {
        if (!activeJobId) return;

        const job = jobs.find(j => j.id === activeJobId);
        if (job) {
            if (job.status === 'completed') {
                handleJobClick(job);
                dispatch(setActiveJobId(null));
                toast.success('✨ Job completed! Result loaded.');
            } else if (job.status === 'failed') {
                dispatch(setActiveJobId(null));
                toast.error(`Job failed: ${job.error}`);
            }
        }
    }, [activeJobId, jobs, dispatch]);

    const handleAnalyzeAndTransform = async () => {
        if (!previewTableId) return;

        setIsAnalyzing(true);
        dispatch(setTransformedPreview(null));
        dispatch(setAnalysisResult(null));

        try {
            // Step 1: Submit analysis job with metadata for recovery
            const fileName = selectedFile?.name || 'Unknown File';
            const sheetSuffix = selectedSheet ? ` - ${selectedSheet}` : '';
            const displayName = fileName.replace(/\.(xlsx|xls|csv)$/i, '') + sheetSuffix;

            const metadata = {
                selectedFile: selectedFile ? {
                    id: selectedFile.id,
                    name: selectedFile.name,
                    path: selectedFile.path,
                    downloadUrl: selectedFile.downloadUrl,
                    webUrl: selectedFile.webUrl,
                    size: selectedFile.size,
                    lastModified: selectedFile.lastModified
                } : undefined,
                selectedSheet: selectedSheet || undefined,
                displayName: displayName
            };
            // Job submission with metadata
            const response = await api.analyzeFile(previewTableId, transformInput || undefined, metadata);
            const jobId = response.data.job_id;

            dispatch(setActiveJobId(jobId));
            refreshJobs();
            toast.info("🚀 Analysis job started...");

        } catch (error: any) {
            toast.error(`Failed to start analysis: ${error.response?.data?.detail || error.message}`);
            setIsAnalyzing(false);
        }
    };

    const handleRefine = async () => {
        if (!previewTableId || !analysisResult?.transform_code || !feedbackInput.trim()) return;

        setIsRefining(true);
        try {
            // Refine the transform code (starts a job)
            const res = await api.refineTransform(
                previewTableId,
                analysisResult.transform_code,
                feedbackInput
            );

            setFeedbackInput('');

            if (res.data.job_id) {
                dispatch(setActiveJobId(res.data.job_id));
                refreshJobs();
                toast.success("🔄 Refinement job started! Check the queue.");
            }
        } catch (error: any) {
            toast.error(`Refinement failed: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsRefining(false);
        }
    };

    const handleSave = async (useTransformed: boolean) => {
        if (!previewTableId) return;

        setIsSaving(true);
        try {
            const code = useTransformed && analysisResult?.transform_code
                ? analysisResult.transform_code
                : "# No transformation\npass";

            const displayName = selectedFile?.name.replace(/\.(xlsx|xls|csv)$/i, '') +
                (selectedSheet ? ` - ${selectedSheet}` : '') +
                (useTransformed ? ' (Transformed)' : '');

            await api.confirmTransform(previewTableId, code, displayName);
            toast.success(`✅ Data saved as "${displayName}"`);
            dispatch(fetchTables());

            // Reset for next operation
            resetTransformState();
            dispatch(setPreviewTableId(null));
        } catch (error: any) {
            toast.error(`Save failed: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsSaving(false);
        }
    };

    // Upload to OneDrive



    // Reset all append-related state
    const resetAppendState = () => {
        setAppendValidation(null);
        setAppendTransformPreview(null);
        setTransformFeedback('');
        setMappingDescription('');
        setAppendError(null);
    };

    // Generate NEW transform to match target schema (when no stored transform exists)
    const handleGenerateTransform = async () => {
        if (!previewTableId || !targetTableId) return;

        setIsGeneratingTransform(true);
        setAppendTransformPreview(null);

        try {
            const response = await api.generateAppendTransform(
                previewTableId,
                targetTableId,
                mappingDescription || ''
            );
            setAppendTransformPreview(response.data);

            if (response.data.success) {
                if (response.data.generated_code) {
                    setGeneratedTransformCode(response.data.generated_code);
                }
                toast.success('✨ Transform generated successfully!');
            } else {
                toast.error('Transform generation failed - try adding more description');
            }
        } catch (error: any) {
            setAppendTransformPreview({
                success: false,
                preview_data: [],
                preview_columns: [],
                error: error.response?.data?.detail || error.message
            });
            toast.error('Failed to generate transform');
        } finally {
            setIsGeneratingTransform(false);
        }
    };

    // Step 1: Validate append compatibility when target table changes
    const handleValidateAppend = async () => {
        if (!previewTableId || !targetTableId) return;

        setIsValidating(true);
        resetAppendState();

        try {
            const response = await api.validateAppend(previewTableId, targetTableId);
            setAppendValidation(response.data);

            if (response.data.columns_match) {
                toast.success('✅ Columns match! Ready to append.');
            } else if (response.data.compatible && response.data.target_has_transform) {
                toast.info('Transform available - click "Preview Transform" to continue');
            } else {
                toast.warning('Columns do not match and no compatible transform found');
            }
        } catch (error: any) {
            setAppendError(error.response?.data?.detail || error.message);
            toast.error('Validation failed');
        } finally {
            setIsValidating(false);
        }
    };

    // Step 2: Preview the transform applied to source data
    const handlePreviewTransform = async (feedback?: string) => {
        if (!previewTableId || !targetTableId) return;

        setIsPreviewingTransform(true);
        setAppendTransformPreview(null);

        try {
            const response = await api.previewAppendTransform(
                previewTableId,
                targetTableId,
                feedback || transformFeedback || undefined
            );
            setAppendTransformPreview(response.data);

            if (response.data.success) {
                toast.success('✨ Transform preview ready!');
                setTransformFeedback('');
            } else {
                toast.error('Transform failed - provide feedback to fix');
            }
        } catch (error: any) {
            setAppendTransformPreview({
                success: false,
                preview_data: [],
                preview_columns: [],
                error: error.response?.data?.detail || error.message
            });
            toast.error('Preview failed');
        } finally {
            setIsPreviewingTransform(false);
        }
    };

    // Step 3: Confirm and append the transformed data
    const handleConfirmTransformAppend = async () => {
        if (!previewTableId || !targetTableId) return;

        setIsConfirmingTransform(true);
        try {
            const response = await api.confirmAppendTransform(
                previewTableId,
                targetTableId,
                appendDescription || 'Data appended from OneDrive (with transform)',
                generatedTransformCode || undefined
            );
            const data = response.data;

            if (data.error) {
                setAppendError(data.error);
                toast.error('Append failed');
            } else {
                toast.success(`✅ ${data.message}`);
                dispatch(fetchTables());

                // Reset for next operation
                resetTransformState();
                resetAppendState();
                dispatch(setPreviewTableId(null));
                dispatch(setSelectedFile(null));
                dispatch(setTargetTableId(''));
                dispatch(setAppendDescription(''));
                dispatch(setSaveMode('new'));
            }
        } catch (error: any) {
            setAppendError(error.response?.data?.detail || error.message);
            toast.error('Append failed');
        } finally {
            setIsConfirmingTransform(false);
        }
    };

    // Direct append (when columns already match)
    const handleAppend = async () => {
        if (!previewTableId || !targetTableId) {
            toast.error('Please select a target table');
            return;
        }

        setIsAppending(true);
        setAppendError(null);
        try {
            const response = await api.appendToTable(
                targetTableId,
                previewTableId,
                appendDescription || 'Data appended from OneDrive'
            );
            const data = response.data;

            if (data.error) {
                setAppendError(data.error);
                toast.error('Append failed - see error below');
            } else {
                toast.success(`✅ ${data.message}`);
                dispatch(fetchTables());

                // Reset for next operation
                resetTransformState();
                resetAppendState();
                setPreviewTableId(null);
                setSelectedFile(null);
                dispatch(setTargetTableId(''));
                dispatch(setAppendDescription(''));
                dispatch(setSaveMode('new'));
            }
        } catch (error: any) {
            const errorMsg = error.response?.data?.detail || error.message;
            setAppendError(errorMsg);
            toast.error(`Append failed: ${errorMsg}`);
        } finally {
            setIsAppending(false);
        }
    };

    const formatSize = (bytes: number) => {
        return (bytes / 1024 / 1024).toFixed(2) + ' MB';
    };

    if (!status?.configured) {
        return (
            <Card className="bg-card border-border">
                <CardContent className="py-8 text-center">
                    <div className="text-4xl mb-4">☁️</div>
                    <p className="text-muted-foreground">
                        OneDrive not configured: {status?.error || 'Unknown error'}
                    </p>
                    <p className="text-sm text-muted-foreground mt-2">
                        Contact admin to configure OneDrive integration.
                    </p>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-4">
            {/* Jobs Queue - compact mode */}
            <JobStatusList
                jobs={jobs}
                isLoading={isJobsLoading}
                title="Jobs"
                className="mb-4"
                onJobsChange={refreshJobs}
                compact={true}
                defaultCollapsed={true}
            />

            {/* Collapsible File Browser */}
            <Collapsible open={isFileBrowserOpen} onOpenChange={setIsFileBrowserOpen}>
                <Card className="bg-card border-border overflow-hidden">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-lg text-card-foreground flex items-center justify-between">
                            <CollapsibleTrigger className="flex items-center gap-2 cursor-pointer hover:bg-muted/50 transition-colors rounded px-2 py-1 -ml-2">
                                <ChevronDown className={cn(
                                    "w-4 h-4 transition-transform",
                                    !isFileBrowserOpen && "-rotate-90"
                                )} />
                                📂 Files from: {status.root_path}
                            </CollapsibleTrigger>
                            <Button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    loadFiles();
                                }}
                                disabled={isLoading}
                                size="sm"
                            >
                                {isLoading ? <><Spinner />Loading...</> : '🔄 Refresh'}
                            </Button>
                        </CardTitle>
                    </CardHeader>
                    <CollapsibleContent>
                        <CardContent className="space-y-4">
                            {/* File List - Grouped by Folder */}
                            {files.length === 0 ? (
                                <p className="text-muted-foreground">
                                    Klik 'Refresh' untuk memuat file dari OneDrive.
                                </p>
                            ) : (
                                <ScrollArea className="h-[400px]">
                                    <div className="space-y-3">
                                        {/* Group files by folder */}
                                        {(() => {
                                            const grouped: Record<string, typeof files> = {};
                                            files.forEach(file => {
                                                const folder = file.path.substring(0, file.path.lastIndexOf('/')) || status?.root_path || 'Root';
                                                if (!grouped[folder]) grouped[folder] = [];
                                                grouped[folder].push(file);
                                            });

                                            return Object.entries(grouped).map(([folder, folderFiles]) => (
                                                <Collapsible key={folder} defaultOpen={true}>
                                                    <CollapsibleTrigger className="flex items-center gap-2 w-full p-2 rounded bg-muted/50 hover:bg-muted cursor-pointer">
                                                        <ChevronDown className="w-4 h-4" />
                                                        <span className="font-medium">📁 {folder.split('/').pop() || folder}</span>
                                                        <Badge variant="secondary" className="ml-auto">{folderFiles.length} files</Badge>
                                                    </CollapsibleTrigger>
                                                    <CollapsibleContent>
                                                        <div className="pl-4 mt-1 space-y-1">
                                                            <AnimatePresence>
                                                                {folderFiles.map((file, index) => (
                                                                    <motion.div
                                                                        key={file.id}
                                                                        initial={{ opacity: 0, x: -10 }}
                                                                        animate={{ opacity: 1, x: 0 }}
                                                                        exit={{ opacity: 0, x: 10 }}
                                                                        transition={{ delay: index * 0.02, duration: 0.15 }}
                                                                    >
                                                                        <Button
                                                                            variant="ghost"
                                                                            onClick={() => handleFileClick(file)}
                                                                            className={cn(
                                                                                "w-full h-auto p-2 justify-start items-start text-left font-normal hover:bg-accent hover:text-accent-foreground",
                                                                                selectedFile?.id === file.id
                                                                                    ? "bg-accent text-accent-foreground"
                                                                                    : "text-muted-foreground"
                                                                            )}
                                                                        >
                                                                            <div className="w-full flex justify-between items-center">
                                                                                <span className="font-medium text-foreground truncate pr-2">
                                                                                    {file.name}
                                                                                </span>
                                                                                <span className="text-xs opacity-70 flex-shrink-0">{formatSize(file.size)}</span>
                                                                            </div>
                                                                        </Button>
                                                                    </motion.div>
                                                                ))}
                                                            </AnimatePresence>
                                                        </div>
                                                    </CollapsibleContent>
                                                </Collapsible>
                                            ));
                                        })()}
                                    </div>
                                </ScrollArea>
                            )}
                        </CardContent>
                    </CollapsibleContent>
                </Card>
            </Collapsible>


            {/* Selected File Card with Sheet Selection */}
            {
                selectedFile && (
                    <Card className="bg-card border-border">
                        <CardHeader>
                            <CardTitle className="text-lg text-card-foreground">
                                📄 {selectedFile.name}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="text-sm text-muted-foreground">
                                <p>📁 Path: <code className="text-foreground bg-muted px-1 rounded">{selectedFile.path}</code></p>
                                <p>📏 Size: {formatSize(selectedFile.size)}</p>
                            </div>

                            {/* Sheet Selector */}
                            {isFetchingSheets && (
                                <div className="flex items-center gap-2 text-sm text-muted-foreground animate-pulse">
                                    <Spinner />
                                    Fetching sheet list...
                                </div>
                            )}

                            {!isFetchingSheets && sheets.length > 0 && (
                                <div className="space-y-2">
                                    <Label className="text-sm font-medium">Select Sheet:</Label>
                                    <Select value={selectedSheet} onValueChange={(val) => dispatch(setSelectedSheet(val))}>
                                        <SelectTrigger className="w-full">
                                            <SelectValue placeholder="Select sheet..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {sheets.map((sheet) => (
                                                <SelectItem key={sheet} value={sheet}>
                                                    {sheet}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            )}

                            <Button
                                onClick={handleLoadSheet}
                                disabled={isLoadingSheet || (sheets.length > 0 && !selectedSheet)}
                                className="w-full sm:w-auto"
                            >
                                {isLoadingSheet ? (
                                    <>
                                        <Spinner />
                                        Loading...
                                    </>
                                ) : (
                                    '📥 Load Sheet'
                                )}
                            </Button>
                        </CardContent>
                    </Card>
                )
            }

            {/* ===== STEP 2: Original Data Preview + Transform Input ===== */}
            {
                previewTableId && !analysisResult && (
                    <div className="space-y-4">
                        {showSuccessAlert && (
                            <Alert className="border-green-500/50 bg-green-500/10">
                                <CheckCircle className="h-4 w-4 text-green-500" />
                                <AlertTitle className="text-green-600 flex justify-between items-center">
                                    <span>Data Loaded Successfully!</span>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => setShowSuccessAlert(false)}
                                        className="h-6 w-6 hover:bg-green-500/20 text-green-600"
                                    >
                                        <X className="h-4 w-4" />
                                    </Button>
                                </AlertTitle>
                                <AlertDescription className="text-muted-foreground">
                                    Raw data preview. You can transform or save immediately.
                                </AlertDescription>
                            </Alert>
                        )}

                        <DataPreview tableId={previewTableId} title="Raw Data Preview" />

                        {/* Save Mode Selection */}
                        <Card className="bg-card border-border">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-base flex items-center gap-2">
                                    💾 How to Save This Data?
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <RadioGroup
                                    value={saveMode}
                                    onValueChange={(value: 'new' | 'append') => {
                                        dispatch(setSaveMode(value));
                                        setAppendError(null);
                                    }}
                                    className="flex gap-6"
                                >
                                    <div className="flex items-center space-x-2">
                                        <RadioGroupItem value="new" id="onedrive-save-new" />
                                        <Label htmlFor="onedrive-save-new">Create New Table</Label>
                                    </div>
                                    <div className="flex items-center space-x-2">
                                        <RadioGroupItem value="append" id="onedrive-save-append" />
                                        <Label htmlFor="onedrive-save-append">Append to Existing Table</Label>
                                    </div>
                                </RadioGroup>

                                {/* Append Mode: Smart Append Flow */}
                                {saveMode === 'append' && (
                                    <div className="space-y-3 pt-2 border-t border-border">
                                        {/* Step 1: Table Selector */}
                                        <div className="space-y-2">
                                            <Label>Target Table:</Label>
                                            <div className="flex gap-2">
                                                <Select
                                                    value={targetTableId}
                                                    onValueChange={(value) => {
                                                        dispatch(setTargetTableId(value));
                                                        resetAppendState();
                                                    }}
                                                >
                                                    <SelectTrigger className="flex-1">
                                                        <SelectValue placeholder="Select a table to append to..." />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {tables.map((table) => (
                                                            <SelectItem key={table.cache_path} value={table.cache_path}>
                                                                {table.display_name} ({table.n_rows} rows)
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                                <Button
                                                    onClick={handleValidateAppend}
                                                    disabled={!targetTableId || isValidating}
                                                    variant="outline"
                                                    className="gap-2"
                                                >
                                                    {isValidating ? <Spinner /> : <RefreshCw className="w-4 h-4" />}
                                                    Check
                                                </Button>
                                            </div>
                                        </div>

                                        {/* Validation Results */}
                                        {appendValidation && (
                                            <div className="space-y-3">
                                                {/* Columns Match - Ready to Append */}
                                                {appendValidation.columns_match && (
                                                    <Alert className="border-green-500/50 bg-green-500/10">
                                                        <CheckCircle className="h-4 w-4 text-green-500" />
                                                        <AlertTitle className="text-green-600">Ready to Append</AlertTitle>
                                                        <AlertDescription className="text-sm">
                                                            Columns match! You can directly append this data.
                                                        </AlertDescription>
                                                    </Alert>
                                                )}

                                                {/* Columns Don't Match - Show Issues */}
                                                {!appendValidation.columns_match && (
                                                    <>
                                                        <Alert variant="destructive" className="mt-2">
                                                            <AlertTriangle className="h-4 w-4" />
                                                            <AlertTitle>Column Mismatch</AlertTitle>
                                                            <AlertDescription className="text-sm space-y-1">
                                                                {appendValidation.issues.map((issue, i) => (
                                                                    <div key={i}>• {issue}</div>
                                                                ))}
                                                            </AlertDescription>
                                                        </Alert>

                                                        {/* LLM Compatibility Assessment */}
                                                        {appendValidation.similarity_reason && (
                                                            <Alert className={appendValidation.compatible ? "border-blue-500/50 bg-blue-500/10" : "border-amber-500/50 bg-amber-500/10"}>
                                                                {appendValidation.compatible ? (
                                                                    <Wand2 className="h-4 w-4 text-blue-500" />
                                                                ) : (
                                                                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                                                                )}
                                                                <AlertTitle className={appendValidation.compatible ? "text-blue-600" : "text-amber-600"}>
                                                                    {appendValidation.compatible ? "Transform Available" : "Transform May Not Work"}
                                                                </AlertTitle>
                                                                <AlertDescription className="text-sm">
                                                                    {appendValidation.similarity_reason}
                                                                </AlertDescription>
                                                            </Alert>
                                                        )}

                                                        {/* Transform Explanation */}
                                                        {/* Option 1: Stored Transform (if available) */}
                                                        {appendValidation.target_has_transform && (
                                                            <div className="rounded-md border p-3 bg-muted/40 space-y-3">
                                                                <div className="flex items-center justify-between">
                                                                    <div className="flex items-center gap-2">
                                                                        <Badge variant="secondary" className="text-xs">Stored Transform</Badge>
                                                                        {appendValidation.compatible && (
                                                                            <span className="text-xs text-green-600 flex items-center gap-1">
                                                                                <CheckCircle className="w-3 h-3" /> Compatible
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                </div>

                                                                {appendValidation.transform_explanation && (
                                                                    <p className="text-xs text-muted-foreground">
                                                                        {appendValidation.transform_explanation}
                                                                    </p>
                                                                )}

                                                                <Button
                                                                    onClick={() => handlePreviewTransform()}
                                                                    disabled={isPreviewingTransform}
                                                                    className="w-full gap-2"
                                                                    variant="outline"
                                                                >
                                                                    {isPreviewingTransform ? <Spinner /> : <RefreshCw className="w-4 h-4" />}
                                                                    Apply Stored Transform
                                                                </Button>
                                                            </div>
                                                        )}

                                                        {/* Option 2: Generate New Transform */}
                                                        <div className={`space-y-2 ${appendValidation.target_has_transform ? "pt-2 border-t border-dashed" : ""}`}>
                                                            <Label className="text-sm font-medium flex items-center justify-between">
                                                                <span>{appendValidation.target_has_transform ? "Or Generate New Transform" : "Generate Transform"}</span>
                                                                <Badge variant="outline" className="text-[10px] font-normal">AI Powered</Badge>
                                                            </Label>
                                                            <Textarea
                                                                placeholder="e.g. Map 'CustName' to 'Customer', 'InvDate' to 'Date'..."
                                                                value={mappingDescription}
                                                                onChange={(e) => setMappingDescription(e.target.value)}
                                                                className="text-xs min-h-[60px] resize-none"
                                                            />
                                                            <Button
                                                                onClick={handleGenerateTransform}
                                                                disabled={isGeneratingTransform}
                                                                className="w-full gap-2"
                                                                variant={appendValidation.target_has_transform ? "secondary" : "default"}
                                                            >
                                                                {isGeneratingTransform ? <Spinner /> : <Wand2 className="w-4 h-4" />}
                                                                Generate & Preview
                                                            </Button>
                                                        </div>
                                                    </>
                                                )}
                                            </div>
                                        )}

                                        {/* Transform Preview */}
                                        {appendTransformPreview && (
                                            <div className="space-y-3">
                                                {appendTransformPreview.success ? (
                                                    <>
                                                        <Alert className="border-green-500/50 bg-green-500/10">
                                                            <CheckCircle className="h-4 w-4 text-green-500" />
                                                            <AlertTitle className="text-green-600">Transform Successful</AlertTitle>
                                                            <AlertDescription className="text-sm">
                                                                Preview of transformed data below. Click &quot;Confirm Append&quot; to proceed.
                                                            </AlertDescription>
                                                        </Alert>

                                                        {/* Preview Table */}
                                                        <Card className="border-primary/20 bg-primary/5">
                                                            <CardHeader className="py-3 px-4">
                                                                <div className="flex justify-between items-center">
                                                                    <CardTitle className="text-sm">Transformed Preview</CardTitle>
                                                                    <Badge variant="secondary" className="text-[10px] h-5">
                                                                        {appendTransformPreview.preview_data.length} rows
                                                                    </Badge>
                                                                </div>
                                                            </CardHeader>
                                                            <CardContent className="p-4 pt-0">
                                                                <ScrollArea className="h-[200px] rounded-md border bg-background">
                                                                    <div className="min-w-max p-1">
                                                                        <Table>
                                                                            <TableHeader>
                                                                                <TableRow>
                                                                                    {appendTransformPreview.preview_columns.map((col) => (
                                                                                        <TableHead key={col} className="whitespace-nowrap text-xs font-medium">
                                                                                            {col}
                                                                                        </TableHead>
                                                                                    ))}
                                                                                </TableRow>
                                                                            </TableHeader>
                                                                            <TableBody>
                                                                                {appendTransformPreview.preview_data.slice(0, 10).map((row, idx) => (
                                                                                    <TableRow key={idx}>
                                                                                        {appendTransformPreview.preview_columns.map((col) => (
                                                                                            <TableCell key={col} className="text-xs py-1">
                                                                                                {String(row[col] ?? '')}
                                                                                            </TableCell>
                                                                                        ))}
                                                                                    </TableRow>
                                                                                ))}
                                                                            </TableBody>
                                                                        </Table>
                                                                    </div>
                                                                    <ScrollBar orientation="horizontal" />
                                                                </ScrollArea>
                                                            </CardContent>
                                                        </Card>
                                                    </>
                                                ) : (
                                                    <>
                                                        <Alert variant="destructive">
                                                            <AlertTriangle className="h-4 w-4" />
                                                            <AlertTitle>Transform Failed</AlertTitle>
                                                            <AlertDescription className="text-sm whitespace-pre-line">
                                                                {appendTransformPreview.error}
                                                            </AlertDescription>
                                                        </Alert>

                                                        {/* Feedback Input for Retry */}
                                                        <div className="space-y-2">
                                                            <Label>Describe how to fix the transform:</Label>
                                                            <Textarea
                                                                placeholder="e.g., 'Skip the first 2 rows', 'Use different date format', etc."
                                                                value={transformFeedback}
                                                                onChange={(e) => setTransformFeedback(e.target.value)}
                                                                rows={2}
                                                                className="resize-none"
                                                            />
                                                            <Button
                                                                onClick={() => handlePreviewTransform(transformFeedback)}
                                                                disabled={!transformFeedback.trim() || isPreviewingTransform}
                                                                className="gap-2"
                                                            >
                                                                {isPreviewingTransform ? (
                                                                    <><Spinner />Retrying...</>
                                                                ) : (
                                                                    <><RefreshCw className="w-4 h-4" />Retry Transform</>
                                                                )}
                                                            </Button>
                                                        </div>
                                                    </>
                                                )}
                                            </div>
                                        )}

                                        {/* Description Input */}
                                        <div className="space-y-2">
                                            <Label>Description (optional):</Label>
                                            <Textarea
                                                placeholder="Describe this batch of data, e.g., 'December 2024 sales data'"
                                                value={appendDescription}
                                                onChange={(e) => dispatch(setAppendDescription(e.target.value))}
                                                rows={2}
                                                className="resize-none"
                                            />
                                        </div>

                                        {/* General Error Display */}
                                        {appendError && (
                                            <Alert variant="destructive" className="mt-2">
                                                <AlertTriangle className="h-4 w-4" />
                                                <AlertTitle>Error</AlertTitle>
                                                <AlertDescription className="whitespace-pre-line text-sm">
                                                    {appendError}
                                                </AlertDescription>
                                            </Alert>
                                        )}

                                        {/* Action Buttons */}
                                        <div className="flex gap-2 flex-wrap">
                                            {/* Direct Append (columns match) */}
                                            {appendValidation?.columns_match && (
                                                <Button
                                                    onClick={handleAppend}
                                                    disabled={isAppending}
                                                    className="gap-2"
                                                >
                                                    {isAppending ? (
                                                        <><Spinner />Appending...</>
                                                    ) : (
                                                        <><Save className="w-4 h-4" />📥 Append to Table</>
                                                    )}
                                                </Button>
                                            )}

                                            {/* Confirm Transform Append */}
                                            {appendTransformPreview?.success && (
                                                <Button
                                                    onClick={handleConfirmTransformAppend}
                                                    disabled={isConfirmingTransform}
                                                    className="gap-2"
                                                >
                                                    {isConfirmingTransform ? (
                                                        <><Spinner />Appending...</>
                                                    ) : (
                                                        <><CheckCircle className="w-4 h-4" />✨ Confirm Append</>
                                                    )}
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Upload to OneDrive Card */}


                        {/* Transform Input Section - Only for "New Table" mode */}
                        {saveMode === 'new' && (
                            <Card className="bg-card border-border">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <Wand2 className="w-4 h-4 text-primary" />
                                        Data Transformation (Optional)
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <Textarea
                                        placeholder="Example: Remove empty rows, Change date format to DD/MM/YYYY, Filter only this month's data..."
                                        value={transformInput}
                                        onChange={(e) => dispatch(setTransformInput(e.target.value))}
                                        rows={3}
                                        className="resize-none"
                                    />
                                    <div className="flex flex-wrap gap-2">
                                        <Button
                                            onClick={handleAnalyzeAndTransform}
                                            disabled={isAnalyzing}
                                            className="gap-2"
                                        >
                                            {isAnalyzing ? (
                                                <>
                                                    <Spinner />
                                                    Analyzing...
                                                </>
                                            ) : (
                                                <>
                                                    <Wand2 className="w-4 h-4" />
                                                    ✨ Analyze & Transform
                                                </>
                                            )}
                                        </Button>

                                        <Button
                                            variant="outline"
                                            onClick={() => handleSave(false)}
                                            disabled={isSaving}
                                            className="gap-2"
                                        >
                                            {isSaving ? (
                                                <>
                                                    <Spinner />
                                                    Saving...
                                                </>
                                            ) : (
                                                <>
                                                    <Save className="w-4 h-4" />
                                                    💾 Save As New Table
                                                </>
                                            )}
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        )}
                    </div>
                )
            }

            {/* ===== STEP 3: Transformed Data Preview + Feedback ===== */}
            {
                analysisResult && (
                    <div className="space-y-4">
                        {/* Collapsible Original Data Preview */}
                        <Collapsible open={isOriginalPreviewExpanded} onOpenChange={setIsOriginalPreviewExpanded}>
                            <Card className="bg-card border-border overflow-hidden">
                                <CollapsibleTrigger className="w-full cursor-pointer">
                                    <CardHeader className="py-3">
                                        <CardTitle className="text-sm font-medium flex items-center gap-2">
                                            <ChevronDown className={cn(
                                                "w-4 h-4 transition-transform",
                                                !isOriginalPreviewExpanded && "-rotate-90"
                                            )} />
                                            Raw Data Inspector
                                        </CardTitle>
                                    </CardHeader>
                                </CollapsibleTrigger>
                                <CollapsibleContent>
                                    <CardContent className="pt-0">
                                        <DataPreview tableId={previewTableId!} title="" />
                                    </CardContent>
                                </CollapsibleContent>
                            </Card>
                        </Collapsible>

                        {/* Issues Found */}
                        {analysisResult.issues_found && analysisResult.issues_found.length > 0 && (
                            <Card className="border-amber-500/50 bg-amber-500/10">
                                <CardHeader className="py-2 pb-1">
                                    <CardTitle className="text-sm flex items-center gap-2 text-amber-600">
                                        <AlertTriangle className="w-4 h-4" />
                                        Data Quality Issues Detected
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="pt-0 pb-3">
                                    <ul className="text-sm space-y-0.5">
                                        {analysisResult.issues_found.map((issue, i) => (
                                            <li key={i} className="flex items-start gap-1.5">
                                                <span className="text-muted-foreground">•</span>
                                                <span>{issue}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </CardContent>
                            </Card>
                        )}

                        {/* Transform Code (Collapsible) */}
                        <Collapsible open={isCodeExpanded} onOpenChange={setIsCodeExpanded}>
                            <Card className="bg-card border-border overflow-hidden">
                                <CollapsibleTrigger className="w-full cursor-pointer">
                                    <CardHeader className="py-2">
                                        <CardTitle className="text-sm flex items-center gap-2">
                                            <ChevronDown className={cn(
                                                "w-4 h-4 transition-transform",
                                                !isCodeExpanded && "-rotate-90"
                                            )} />
                                            <Code className="w-4 h-4" />
                                            Transform Logic (Python)
                                        </CardTitle>
                                    </CardHeader>
                                </CollapsibleTrigger>
                                <CollapsibleContent>
                                    <CardContent className="pt-0">
                                        <pre className="p-3 bg-muted rounded text-xs overflow-x-auto">
                                            <code>{analysisResult.transform_code}</code>
                                        </pre>
                                    </CardContent>
                                </CollapsibleContent>
                            </Card>
                        </Collapsible>

                        {/* Transformed Preview - Collapsible like Original */}
                        {transformedPreview && (
                            <Collapsible open={isTransformedPreviewExpanded} onOpenChange={setIsTransformedPreviewExpanded}>
                                <Card className="bg-card border-border overflow-hidden">
                                    <CollapsibleTrigger className="w-full cursor-pointer">
                                        <CardHeader className="py-3">
                                            <CardTitle className="text-sm font-medium flex items-center gap-2">
                                                <ChevronDown className={cn(
                                                    "w-4 h-4 transition-transform",
                                                    !isTransformedPreviewExpanded && "-rotate-90"
                                                )} />
                                                📊 Transformed Data Preview
                                            </CardTitle>
                                        </CardHeader>
                                    </CollapsibleTrigger>
                                    <CollapsibleContent>
                                        <CardContent className="pt-0">
                                            {/* Inner Card matching DataPreview styling */}
                                            <Card className="mt-4 border-primary/20 bg-primary/5">
                                                <CardHeader className="py-4 px-6">
                                                    <div className="flex justify-between items-center">
                                                        <h3 className="text-sm font-medium leading-none tracking-tight flex items-center gap-2">
                                                            Table Data
                                                        </h3>
                                                        <Badge variant="secondary" className="text-[10px] h-5 font-normal">
                                                            {transformedPreview.preview_data.length} rows shown
                                                        </Badge>
                                                    </div>
                                                </CardHeader>
                                                <CardContent className="p-6 pt-0">
                                                    <div className="rounded-md border bg-background">
                                                        <ScrollArea className="h-[400px] w-full rounded-md">
                                                            <div className="min-w-max p-1">
                                                                <Table>
                                                                    <TableHeader>
                                                                        <TableRow>
                                                                            {transformedPreview.columns.map((col) => (
                                                                                <TableHead key={col} className="bg-muted/50 px-3 py-2 font-semibold text-xs whitespace-nowrap sticky top-0 z-10">
                                                                                    {col}
                                                                                </TableHead>
                                                                            ))}
                                                                        </TableRow>
                                                                    </TableHeader>
                                                                    <TableBody>
                                                                        {transformedPreview.preview_data.map((row, i) => (
                                                                            <TableRow key={i} className="hover:bg-muted/50 transition-colors">
                                                                                {transformedPreview.columns.map((col) => {
                                                                                    const cellValue = String(row[col] ?? "");
                                                                                    const isTruncated = cellValue.length > 50;
                                                                                    return (
                                                                                        <TableCell key={col} className="px-3 py-2 border-r last:border-r-0 whitespace-nowrap">
                                                                                            {isTruncated ? (
                                                                                                <Tooltip>
                                                                                                    <TooltipTrigger asChild>
                                                                                                        <span className="truncate block decoration-dotted underline underline-offset-2 decoration-muted-foreground/30 max-w-[250px]">{cellValue}</span>
                                                                                                    </TooltipTrigger>
                                                                                                    <TooltipContent className="max-w-md p-3">
                                                                                                        <p className="whitespace-pre-wrap font-mono text-xs">{cellValue}</p>
                                                                                                    </TooltipContent>
                                                                                                </Tooltip>
                                                                                            ) : (
                                                                                                <span className="block">{cellValue}</span>
                                                                                            )}
                                                                                        </TableCell>
                                                                                    );
                                                                                })}
                                                                            </TableRow>
                                                                        ))}
                                                                    </TableBody>
                                                                </Table>
                                                            </div>
                                                            <ScrollBar orientation="horizontal" />
                                                            <ScrollBar orientation="horizontal" />
                                                            <ScrollBar orientation="vertical" />
                                                        </ScrollArea>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        </CardContent>
                                    </CollapsibleContent>
                                </Card>
                            </Collapsible>
                        )}

                        {/* Feedback & Actions */}
                        <Card className="bg-card border-border">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-base flex items-center gap-2">
                                    <RefreshCw className="w-4 h-4 text-primary" />
                                    Feedback / Refinement
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <Textarea
                                    placeholder="Example: Change date format, Remove column X, Replace null values with 0..."
                                    value={feedbackInput}
                                    onChange={(e) => setFeedbackInput(e.target.value)}
                                    rows={2}
                                    className="resize-none"
                                />
                                <div className="flex flex-wrap gap-2">
                                    <Button
                                        onClick={handleRefine}
                                        disabled={isRefining || !feedbackInput.trim()}
                                        variant="outline"
                                        className="gap-2"
                                    >
                                        {isRefining ? (
                                            <>
                                                <Spinner />
                                                Refining...
                                            </>
                                        ) : (
                                            <>
                                                <RefreshCw className="w-4 h-4" />
                                                🔄 Refine Transform
                                            </>
                                        )}
                                    </Button>

                                    <Button
                                        onClick={() => handleSave(true)}
                                        disabled={isSaving}
                                        className="gap-2"
                                    >
                                        {isSaving ? (
                                            <>
                                                <Spinner />
                                                Saving...
                                            </>
                                        ) : (
                                            <>
                                                <Save className="w-4 h-4" />
                                                💾 Save Transformed
                                            </>
                                        )}
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                )
            }
        </div >
    );
}
