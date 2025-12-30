'use client';

/**
 * Upload Tab Component
 * Upload local files for data analysis with inline transformation
 * 
 * FLOW:
 * 1. Drag & drop or select file → Upload
 * 2. Show preview + text input + (Analyze & Transform | Save As-Is)
 * 3. If analyze clicked → Show transformed preview + code + (Refine | Save)
 */
import { useState, useCallback, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchTables } from '@/store/slices/tablesSlice';
import { RootState } from '@/store';
import { api } from '@/lib/api';
import { motion } from 'framer-motion';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Badge } from "@/components/ui/badge";
import { Label } from '@/components/ui/label';

import { Textarea } from '@/components/ui/textarea';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import { Spinner } from '@/components/ui/spinner';
import { CheckCircle, Wand2, Save, RefreshCw, Code, AlertTriangle, ChevronDown, X, Upload, Cloud } from 'lucide-react';
import { cn } from '@/lib/utils';

import { DataPreview } from '@/components/DataPreview';
import { useUserJobs } from '@/hooks/useUserJobs';
import { JobStatusList } from '@/components/JobStatusList';

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

export default function UploadTab() {
    const dispatch = useAppDispatch();
    const [isUploading, setIsUploading] = useState(false);
    const [dragOver, setDragOver] = useState(false);

    // Job polling
    const { jobs, isLoading: isJobsLoading, refresh: refreshJobs } = useUserJobs();

    // activeJobId for auto-loading results
    const [activeJobId, setActiveJobId] = useState<string | null>(null);


    // Preview state (original data)
    const [previewTableId, setPreviewTableId] = useState<string | null>(null);
    const [uploadedFileName, setUploadedFileName] = useState<string>('');

    // Transform workflow state
    const [transformInput, setTransformInput] = useState('');
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
    const [transformedPreview, setTransformedPreview] = useState<TransformPreview | null>(null);
    const [feedbackInput, setFeedbackInput] = useState('');
    const [isRefining, setIsRefining] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [showSuccessAlert, setShowSuccessAlert] = useState(true);
    const [isCodeExpanded, setIsCodeExpanded] = useState(false);

    // Collapsible state for original preview (auto-collapse after transform)
    const [isOriginalPreviewExpanded, setIsOriginalPreviewExpanded] = useState(true);
    const [isTransformedPreviewExpanded, setIsTransformedPreviewExpanded] = useState(true);

    // Save mode: 'new' creates new table, 'append' appends to existing
    const [saveMode, setSaveMode] = useState<'new' | 'append'>('new');
    const [targetTableId, setTargetTableId] = useState<string>('');
    const [appendDescription, setAppendDescription] = useState('');
    const [isAppending, setIsAppending] = useState(false);
    const [appendError, setAppendError] = useState<string | null>(null);

    // Get existing tables for append target selection
    const tables = useAppSelector((state: RootState) => state.tables.tables);

    // OneDrive upload state
    const [oneDriveSubfolders, setOneDriveSubfolders] = useState<{ id: string, name: string, childCount: number }[]>([]);
    const [selectedOneDriveFolder, setSelectedOneDriveFolder] = useState<string>('__root__');
    const [uploadFilename, setUploadFilename] = useState<string>('');
    const [isUploadingToOneDrive, setIsUploadingToOneDrive] = useState(false);
    const [isLoadingFolders, setIsLoadingFolders] = useState(false);

    useEffect(() => {
        dispatch(fetchTables());
    }, [dispatch]);

    const resetTransformState = () => {
        setTransformInput('');
        setAnalysisResult(null);
        setTransformedPreview(null);
        setFeedbackInput('');
    };

    const handleFileUpload = async (file: File) => {
        if (!file) return;

        // Validate file type
        const validTypes = ['.csv', '.xlsx', '.xls'];
        const ext = '.' + file.name.split('.').pop()?.toLowerCase();

        if (!validTypes.includes(ext)) {
            toast.error('File type not supported. Please use CSV or Excel.');
            return;
        }

        setIsUploading(true);
        resetTransformState();
        setPreviewTableId(null);

        try {
            const response = await api.uploadFile(file);
            toast.success(`File "${file.name}" uploaded - ready to preview`);
            if (response.data.cache_path) {
                setPreviewTableId(response.data.cache_path);
                setUploadedFileName(file.name);
            }
            // Note: Don't dispatch(fetchTables()) here - table appears in Manage only after explicit save
        } catch (error: any) {
            toast.error(`Upload failed: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsUploading(false);
        }
    };

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);

        const file = e.dataTransfer.files[0];
        if (file) {
            handleFileUpload(file);
        }
    }, []);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
    }, []);

    const handleJobClick = (job: any) => {
        if (!job.metadata) return;

        // Restore preview table
        if (job.metadata.previewTableId) {
            setPreviewTableId(job.metadata.previewTableId);
            setUploadedFileName(job.metadata.displayName || 'Restored Job');
        }

        // Restore analysis result
        if (job.result) {
            setAnalysisResult({
                summary: job.result.summary || '',
                issues_found: job.result.issues_found || [],
                transform_code: job.result.transform_code || '',
                needs_transform: job.result.needs_transform || false,
                validation_notes: job.result.validation_notes || [],
                explanation: job.result.explanation || '',
                preview_data: job.result.preview_data || [],
                has_error: job.result.has_error || false
            });

            // Restore transformed preview
            if (job.result.preview_data && job.result.preview_columns) {
                setTransformedPreview({
                    columns: job.result.preview_columns,
                    preview_data: job.result.preview_data
                });
            }
        }

        setIsOriginalPreviewExpanded(false);
        toast.success('State restored from completed job');
    };

    // Auto-load completed job result
    useEffect(() => {
        if (!activeJobId) return;

        const job = jobs.find(j => j.id === activeJobId);
        if (job) {
            if (job.status === 'completed') {
                handleJobClick(job);
                setActiveJobId(null);
                toast.success('✨ Job completed! Result loaded.');
            } else if (job.status === 'failed') {
                setActiveJobId(null);
                toast.error(`Job failed: ${job.error}`);
            }
        }
    }, [activeJobId, jobs]);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            handleFileUpload(file);
        }
    };

    const handleAnalyzeAndTransform = async () => {
        if (!previewTableId) return;

        setIsAnalyzing(true);
        setTransformedPreview(null);
        setAnalysisResult(null);

        try {
            // Step 1: Analyze file (starts job)
            const metadata = {
                displayName: uploadedFileName.replace(/\.(xlsx|xls|csv)$/i, ''),
                previewTableId: previewTableId
            };

            const analysisRes = await api.analyzeFile(previewTableId, transformInput || undefined, metadata);

            if (analysisRes.data.job_id) {
                setActiveJobId(analysisRes.data.job_id);
                refreshJobs();
                toast.info("🚀 Analysis job started...");
            }
        } catch (error: any) {
            toast.error(`Analysis failed: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsAnalyzing(false);
        }
    };

    const handleRefine = async () => {
        if (!previewTableId || !analysisResult?.transform_code || !feedbackInput.trim()) return;

        setIsRefining(true);
        try {
            // Refine the transform code
            const refineRes = await api.refineTransform(
                previewTableId,
                analysisResult.transform_code,
                feedbackInput
            );

            setFeedbackInput('');

            if (refineRes.data.job_id) {
                setActiveJobId(refineRes.data.job_id);
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

            const displayName = uploadedFileName.replace(/\.(xlsx|xls|csv)$/i, '') +
                (useTransformed ? ' (Transformed)' : '');

            await api.confirmTransform(previewTableId, code, displayName);
            toast.success(`✅ Data saved as "${displayName}"`);
            dispatch(fetchTables());

            // Reset for next operation
            resetTransformState();
            setPreviewTableId(null);
            setUploadedFileName('');
        } catch (error: any) {
            toast.error(`Save failed: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsSaving(false);
        }
    };

    const loadOneDriveFolders = async () => {
        setIsLoadingFolders(true);
        try {
            const response = await api.listOneDriveSubfolders();
            setOneDriveSubfolders(response.data);
            toast.success(`📁 ${response.data.length} folder ditemukan`);
        } catch (error: any) {
            toast.error(`Gagal memuat folder: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsLoadingFolders(false);
        }
    };

    const handleUploadToOneDrive = async () => {
        if (!previewTableId) {
            toast.error('No data to upload');
            return;
        }

        setIsUploadingToOneDrive(true);
        try {
            const subfolder = selectedOneDriveFolder === '__root__' ? '' : selectedOneDriveFolder;
            const response = await api.uploadToOneDrive(
                previewTableId,
                subfolder,
                uploadFilename || undefined
            );

            if (response.data.success) {
                toast.success(`✅ ${response.data.message}`);
                setUploadFilename('');
            }
        } catch (error: any) {
            toast.error(`Upload gagal: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsUploadingToOneDrive(false);
        }
    };

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
                appendDescription || 'Data appended'
            );
            const data = response.data;

            if (data.error) {
                // Show natural language error from backend
                setAppendError(data.error);
                toast.error('Append failed - see error below');
            } else {
                toast.success(`✅ ${data.message}`);
                dispatch(fetchTables());

                // Reset for next operation
                resetTransformState();
                setPreviewTableId(null);
                setUploadedFileName('');
                setTargetTableId('');
                setAppendDescription('');
                setSaveMode('new');
            }
        } catch (error: any) {
            const errorMsg = error.response?.data?.detail || error.message;
            setAppendError(errorMsg);
            toast.error(`Append failed: ${errorMsg}`);
        } finally {
            setIsAppending(false);
        }
    };

    return (
        <div className="space-y-4">
            <JobStatusList
                jobs={jobs}
                isLoading={isJobsLoading}
                title="Jobs"
                className="mb-4"
                onJobsChange={refreshJobs}
                compact={true}
                defaultCollapsed={true}
            />
            {/* Upload Area */}
            <Card className="bg-card border-border">
                <CardHeader>
                    <CardTitle className="text-lg text-card-foreground">⬆️ Upload File</CardTitle>
                </CardHeader>
                <CardContent>
                    <motion.div
                        onDrop={handleDrop}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        animate={{
                            scale: dragOver ? 1.02 : 1,
                            borderColor: dragOver ? 'var(--primary)' : 'var(--border)'
                        }}
                        transition={{ duration: 0.2 }}
                        className={`
                            border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
                            ${dragOver
                                ? 'border-primary bg-primary/5'
                                : 'border-border hover:border-muted-foreground/50 hover:bg-muted/30'
                            }
                            ${isUploading ? 'opacity-50 pointer-events-none' : ''}
                        `}
                    >
                        <motion.div
                            className="text-4xl mb-4"
                            animate={{ y: dragOver ? -5 : 0 }}
                            transition={{ type: 'spring', stiffness: 300 }}
                        >
                            📁
                        </motion.div>
                        <p className="text-muted-foreground mb-4">
                            Drag & drop files here, or
                        </p>
                        <Input
                            type="file"
                            accept=".csv,.xlsx,.xls"
                            onChange={handleInputChange}
                            className="hidden"
                            id="file-upload"
                            disabled={isUploading}
                        />
                        <div className="flex justify-center">
                            <Label htmlFor="file-upload" className="cursor-pointer">
                                <div className={cn(buttonVariants({ variant: "default" }), isUploading && "opacity-50 pointer-events-none")}>
                                    <span>{isUploading ? <><Spinner />Uploading...</> : 'Choose File'}</span>
                                </div>
                            </Label>
                        </div>
                        <p className="text-sm text-muted-foreground mt-4">
                            Supported formats: CSV, Excel (.xlsx, .xls)
                        </p>
                    </motion.div>
                </CardContent>
            </Card>

            {/* ===== STEP 2: Original Data Preview + Transform Input ===== */}
            {previewTableId && !analysisResult && (
                <div className="space-y-4">
                    {showSuccessAlert && (
                        <Alert className="border-green-500/50 bg-green-500/10">
                            <CheckCircle className="h-4 w-4 text-green-500" />
                            <AlertTitle className="text-green-600 flex justify-between items-center">
                                <span>Upload Successful!</span>
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
                                    setSaveMode(value);
                                    setAppendError(null);
                                }}
                                className="flex gap-6"
                            >
                                <div className="flex items-center space-x-2">
                                    <RadioGroupItem value="new" id="save-new" />
                                    <Label htmlFor="save-new">Create New Table</Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <RadioGroupItem value="append" id="save-append" />
                                    <Label htmlFor="save-append">Append to Existing Table</Label>
                                </div>
                            </RadioGroup>

                            {/* Append Mode: Table Selector */}
                            {saveMode === 'append' && (
                                <div className="space-y-3 pt-2 border-t border-border">
                                    <div className="space-y-2">
                                        <Label>Target Table:</Label>
                                        <Select
                                            value={targetTableId}
                                            onValueChange={setTargetTableId}
                                        >
                                            <SelectTrigger className="w-full">
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
                                    </div>

                                    <div className="space-y-2">
                                        <Label>Description (optional):</Label>
                                        <Textarea
                                            placeholder="Describe this batch of data, e.g., 'December 2024 sales data'"
                                            value={appendDescription}
                                            onChange={(e) => setAppendDescription(e.target.value)}
                                            rows={2}
                                            className="resize-none"
                                        />
                                    </div>

                                    {/* Append Error Display */}
                                    {appendError && (
                                        <Alert variant="destructive" className="mt-2">
                                            <AlertTriangle className="h-4 w-4" />
                                            <AlertTitle>Cannot Append</AlertTitle>
                                            <AlertDescription className="whitespace-pre-line text-sm">
                                                {appendError}
                                            </AlertDescription>
                                        </Alert>
                                    )}

                                    <Button
                                        onClick={handleAppend}
                                        disabled={isAppending || !targetTableId}
                                        className="gap-2"
                                    >
                                        {isAppending ? (
                                            <>
                                                <Spinner />
                                                Appending...
                                            </>
                                        ) : (
                                            <>
                                                <Save className="w-4 h-4" />
                                                📥 Append to Table
                                            </>
                                        )}
                                    </Button>
                                </div>
                            )}
                        </CardContent>
                    </Card>

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
                                    onChange={(e) => setTransformInput(e.target.value)}
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

                    {/* Upload to OneDrive Section */}
                    <Card className="bg-card border-border">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base flex items-center gap-2">
                                <Cloud className="w-4 h-4 text-blue-500" />
                                Upload ke OneDrive
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex gap-2 items-end">
                                <div className="flex-1 space-y-1">
                                    <Label className="text-sm">📁 Pilih Folder Tujuan:</Label>
                                    <Select
                                        value={selectedOneDriveFolder}
                                        onValueChange={setSelectedOneDriveFolder}
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Pilih folder..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="__root__">
                                                📁 Root (Parent Folder)
                                            </SelectItem>
                                            {oneDriveSubfolders.map((folder) => (
                                                <SelectItem key={folder.id} value={folder.name}>
                                                    📁 {folder.name} ({folder.childCount} items)
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <Button
                                    onClick={loadOneDriveFolders}
                                    disabled={isLoadingFolders}
                                    variant="outline"
                                    size="sm"
                                >
                                    {isLoadingFolders ? <><Spinner />Loading...</> : '🔄 Load Folders'}
                                </Button>
                            </div>

                            <div className="space-y-1">
                                <Label className="text-sm">📄 Nama File (opsional):</Label>
                                <Input
                                    placeholder="Kosongkan untuk gunakan nama default..."
                                    value={uploadFilename}
                                    onChange={(e) => setUploadFilename(e.target.value)}
                                />
                            </div>

                            <Button
                                onClick={handleUploadToOneDrive}
                                disabled={isUploadingToOneDrive || !previewTableId}
                                className="gap-2"
                            >
                                {isUploadingToOneDrive ? (
                                    <>
                                        <Spinner />
                                        Uploading...
                                    </>
                                ) : (
                                    <>
                                        <Upload className="w-4 h-4" />
                                        ☁️ Upload ke OneDrive
                                    </>
                                )}
                            </Button>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* ===== STEP 3: Transformed Data Preview + Feedback ===== */}
            {analysisResult && (
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
                                                    <ScrollArea className="h-[300px] w-full rounded-md">
                                                        <div className="min-w-max p-1">
                                                            <Table>
                                                                <TableHeader>
                                                                    <TableRow>
                                                                        {transformedPreview.columns.map((col) => (
                                                                            <TableHead key={col} className="bg-muted/50 px-3 py-1.5 h-7 font-semibold text-xs whitespace-nowrap sticky top-0 z-10">
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
                                                                                const isTruncated = cellValue.length > 60;
                                                                                return (
                                                                                    <TableCell key={col} className="px-3 py-1 border-r last:border-r-0 whitespace-nowrap">
                                                                                        {isTruncated ? (
                                                                                            <Tooltip>
                                                                                                <TooltipTrigger asChild>
                                                                                                    <span className="truncate block max-w-[200px]">{cellValue}</span>
                                                                                                </TooltipTrigger>
                                                                                                <TooltipContent className="max-w-md">
                                                                                                    <p className="whitespace-pre-wrap">{cellValue}</p>
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
            )}
        </div>
    );
}
