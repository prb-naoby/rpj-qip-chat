'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from '@/components/ui/label';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Wand2, Play, Save, AlertTriangle, ChevronDown, Code, Database, ArrowRight, Eye, Sparkles } from 'lucide-react';
import { Spinner } from '@/components/ui/spinner';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { api, pollJobUntilComplete } from '@/lib/api';
import { toast } from 'sonner';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

interface AnalysisDialogProps {
    tableId: string;
    tableName: string;
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
    initialJobResult?: AnalysisResult | null;
}

export interface AnalysisResult {
    summary: string;
    issues_found: string[];
    transform_code: string;
    needs_transform: boolean;
    validation_notes: string[];
    explanation: string;
    preview_data: any[];
    has_error: boolean;
}

export function AnalysisDialog({ tableId, tableName, isOpen, onClose, onSuccess, initialJobResult }: AnalysisDialogProps) {
    const [mode, setMode] = useState<'input' | 'review'>('input');
    const [description, setDescription] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const [result, setResult] = useState<AnalysisResult | null>(null);
    const [editedCode, setEditedCode] = useState('');
    const [feedback, setFeedback] = useState('');
    const [isRefining, setIsRefining] = useState(false);
    const [step, setStep] = useState<'review' | 'previewing' | 'saving'>('review');

    const [previewData, setPreviewData] = useState<{ columns: string[], data: any[] } | null>(null);
    const [rawData, setRawData] = useState<{ columns: string[], data: any[] } | null>(null);
    const [rawDataError, setRawDataError] = useState<string | null>(null);
    const [previewError, setPreviewError] = useState<string | null>(null);
    const [saveMode, setSaveMode] = useState<'replace' | 'new'>('replace');

    const [isCodeExpanded, setIsCodeExpanded] = useState(false);

    // Fetch raw data when opening in review mode
    useEffect(() => {
        if (isOpen && tableId) {
            setRawDataError(null);
            console.log('Fetching raw data for tableId:', tableId);
            api.getTablePreview(tableId, 20)
                .then(res => {
                    console.log('Raw data response:', res.data);
                    // Backend returns { columns, data, total_rows }
                    if (res.data && res.data.data) {
                        setRawData({ columns: res.data.columns, data: res.data.data });
                    } else {
                        setRawDataError('No preview data available');
                    }
                })
                .catch(err => {
                    console.error('Failed to fetch raw data:', err);
                    setRawDataError(err.response?.data?.detail || err.message || 'Failed to load raw data');
                });
        }
    }, [isOpen, tableId]);

    useEffect(() => {
        if (isOpen) {
            if (initialJobResult) {
                setMode('review');
                setResult(initialJobResult);
                setEditedCode(initialJobResult.transform_code || '');
                if (initialJobResult.preview_data) {
                    setPreviewData({
                        columns: Object.keys(initialJobResult.preview_data[0] || {}),
                        data: initialJobResult.preview_data
                    });
                }
            } else {
                setMode('input');
                setDescription('');
            }
        }
    }, [isOpen, initialJobResult]);

    const handleAnalyzeSubmit = async () => {
        setIsSubmitting(true);
        try {
            await api.analyzeFile(tableId, description, { displayName: tableName });
            toast.success("Analysis started in background");
            onClose();
        } catch (error: any) {
            toast.error("Failed to start analysis: " + (error.response?.data?.detail || error.message));
        } finally {
            setIsSubmitting(false);
        }
    };

    const handlePreviewTransform = async () => {
        setStep('previewing');
        setPreviewError(null);
        try {
            // Submit job and get job_id
            const jobResponse = await api.previewTransform(tableId, editedCode);
            const jobId = jobResponse.data.job_id;

            // Poll until complete
            const result = await pollJobUntilComplete(jobId);

            if (result.error) {
                setPreviewError(result.error);
            } else {
                setPreviewData({ columns: result.columns, data: result.preview_data });
            }
        } catch (error: any) {
            setPreviewError(error.message || 'Preview failed');
        } finally {
            setStep('review');
        }
    };

    const handleRefine = async () => {
        if (!feedback.trim()) return;
        setIsRefining(true);
        try {
            await api.refineTransform(tableId, editedCode, feedback);
            toast.success("Refinement job started");
            onClose();
        } catch (error: any) {
            toast.error("Refinement failed: " + (error.response?.data?.detail || error.message));
        } finally {
            setIsRefining(false);
        }
    };

    const handleSave = async () => {
        setStep('saving');
        try {
            const replaceOriginal = saveMode === 'replace';
            await api.confirmTransform(tableId, editedCode, tableName, replaceOriginal);
            toast.success(replaceOriginal ? "Table updated!" : "Saved as new table!");
            onSuccess();
            onClose();
        } catch (error: any) {
            toast.error("Failed to save: " + (error.response?.data?.detail || error.message));
            setStep('review');
        }
    };

    const handleOpenChange = (open: boolean) => {
        if (!open) onClose();
    };

    // Data table renderer
    const renderDataTable = (data: { columns: string[], data: any[] }, height: string = "h-[300px]") => (
        <div className="rounded-md border bg-background overflow-hidden">
            <ScrollArea className={cn(height, "w-full")}>
                <div className="min-w-max">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                {data.columns.map((col) => (
                                    <TableHead key={col} className="bg-muted/50 px-3 py-2 whitespace-nowrap text-xs font-medium sticky top-0 z-10 border-r last:border-r-0">
                                        {col}
                                    </TableHead>
                                ))}
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {data.data.map((row, i) => (
                                <TableRow key={i} className="text-xs hover:bg-muted/20">
                                    {data.columns.map((col) => {
                                        const val = String(row[col] ?? "");
                                        return (
                                            <TableCell key={col} className="px-3 py-1.5 whitespace-nowrap border-r last:border-r-0 max-w-[200px]">
                                                {val.length > 50 ? (
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <span className="truncate block">{val}</span>
                                                        </TooltipTrigger>
                                                        <TooltipContent className="max-w-md">
                                                            <p className="whitespace-pre-wrap text-xs">{val}</p>
                                                        </TooltipContent>
                                                    </Tooltip>
                                                ) : val}
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
    );

    return (
        <Dialog open={isOpen} onOpenChange={handleOpenChange}>
            <DialogContent className="max-w-[98vw] sm:max-w-[98vw] md:max-w-[98vw] lg:max-w-[98vw] xl:max-w-[98vw] w-[98vw] h-[95vh] flex flex-col p-0 gap-0">
                {/* Header */}
                <DialogHeader className="px-6 py-3 border-b shrink-0">
                    <DialogTitle className="flex items-center gap-2 text-lg">
                        <Wand2 className="w-5 h-5 text-primary" />
                        AI Data Analyst: {tableName}
                    </DialogTitle>
                    <DialogDescription className="text-sm">
                        {mode === 'input' ? "Start a new analysis to clean and transform your data." : "Review analysis results and confirm transformations."}
                    </DialogDescription>
                </DialogHeader>

                {/* Body */}
                <div className="flex-1 overflow-hidden">
                    {mode === 'input' && (
                        <div className="h-full grid grid-cols-2 gap-4 p-4 overflow-hidden">
                            {/* Left Panel: Analysis Configuration */}
                            <div className="flex flex-col gap-3">
                                <Card className="shrink-0">
                                    <CardHeader className="py-3">
                                        <CardTitle className="text-base flex items-center gap-2">
                                            <Sparkles className="w-4 h-4 text-primary" />
                                            Analysis Configuration
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg border border-blue-200 dark:border-blue-800">
                                            <p className="text-sm text-blue-800 dark:text-blue-200 mb-2 font-medium">What happens next?</p>
                                            <ul className="text-sm text-blue-700 dark:text-blue-300 space-y-1 list-disc list-inside">
                                                <li>AI will scan the dataset for quality issues</li>
                                                <li>Runs in the background - you can close this window</li>
                                                <li>Results will appear in the Jobs list when ready</li>
                                            </ul>
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Optional: Describe specific issues or cleaning rules</Label>
                                            <Textarea
                                                placeholder="e.g. Remove rows where 'Status' is empty, Convert 'Date' to datetime..."
                                                value={description}
                                                onChange={(e) => setDescription(e.target.value)}
                                                rows={8}
                                                className="resize-none"
                                            />
                                            <Button
                                                onClick={handleAnalyzeSubmit}
                                                disabled={isSubmitting}
                                                className="w-full gap-2"
                                            >
                                                {isSubmitting ? <Spinner className="w-4 h-4" /> : <Wand2 className="w-4 h-4" />}
                                                Analyze
                                            </Button>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>

                            {/* Right Panel: Data Preview */}
                            <div className="flex flex-col gap-3 overflow-hidden">
                                <Card className="flex-1 flex flex-col overflow-hidden">
                                    <CardHeader className="py-3 shrink-0">
                                        <CardTitle className="text-base flex items-center gap-2">
                                            <Database className="w-4 h-4 text-muted-foreground" />
                                            Current Data
                                        </CardTitle>
                                        <p className="text-xs text-muted-foreground">Preview of your table (First 20 rows)</p>
                                    </CardHeader>
                                    <CardContent className="flex-1 overflow-hidden p-3">
                                        {rawDataError ? (
                                            <Alert variant="destructive">
                                                <AlertTitle className="text-sm">Failed to Load</AlertTitle>
                                                <AlertDescription className="text-xs">{rawDataError}</AlertDescription>
                                            </Alert>
                                        ) : rawData ? (
                                            <div className="h-full rounded-md border bg-background overflow-hidden">
                                                <ScrollArea className="h-full w-full">
                                                    <div className="min-w-max">
                                                        <Table>
                                                            <TableHeader>
                                                                <TableRow>
                                                                    {rawData.columns.map((col) => (
                                                                        <TableHead key={col} className="bg-muted/50 px-3 py-2 whitespace-nowrap font-medium sticky top-0 z-10 text-xs">
                                                                            {col}
                                                                        </TableHead>
                                                                    ))}
                                                                </TableRow>
                                                            </TableHeader>
                                                            <TableBody>
                                                                {rawData.data.map((row, i) => (
                                                                    <TableRow key={i} className="text-xs hover:bg-muted/20">
                                                                        {rawData.columns.map((col) => (
                                                                            <TableCell key={col} className="px-3 py-1.5 whitespace-nowrap text-xs">
                                                                                {String(row[col] ?? "")}
                                                                            </TableCell>
                                                                        ))}
                                                                    </TableRow>
                                                                ))}
                                                            </TableBody>
                                                        </Table>
                                                    </div>
                                                    <ScrollBar orientation="horizontal" />
                                                    <ScrollBar orientation="vertical" />
                                                </ScrollArea>
                                            </div>
                                        ) : (
                                            <div className="h-full flex items-center justify-center text-muted-foreground text-sm border rounded-md">
                                                <Spinner className="w-4 h-4 mr-2" /> Loading preview...
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    )}

                    {mode === 'review' && result && (
                        <div className="h-full grid grid-cols-2 gap-4 p-4 overflow-hidden">
                            {/* Left Panel: Analysis Info + Code */}
                            <div className="flex flex-col gap-3 overflow-y-auto pr-2">
                                {/* Summary */}
                                <Card className="shrink-0">
                                    <CardHeader className="py-3">
                                        <CardTitle className="text-sm flex items-center gap-2">
                                            <Wand2 className="w-4 h-4 text-purple-500" />
                                            Analysis Summary
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="py-0 pb-3">
                                        <p className="text-sm text-muted-foreground leading-relaxed bg-muted/30 p-3 rounded-md">
                                            {result.summary}
                                        </p>
                                    </CardContent>
                                </Card>

                                {/* Issues */}
                                {result.issues_found?.length > 0 && (
                                    <Card className="border-amber-300/50 shrink-0">
                                        <CardHeader className="py-3">
                                            <CardTitle className="text-sm flex items-center gap-2 text-amber-600">
                                                <AlertTriangle className="w-4 h-4" />
                                                Issues Detected ({result.issues_found.length})
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="py-0 pb-3">
                                            <ul className="text-xs space-y-1.5">
                                                {result.issues_found.map((issue, i) => (
                                                    <li key={i} className="flex items-start gap-2 bg-amber-50/50 dark:bg-amber-900/10 p-2 rounded text-amber-900 dark:text-amber-100">
                                                        <span className="text-amber-500">•</span>
                                                        <span>{issue}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        </CardContent>
                                    </Card>
                                )}

                                {/* Refine */}
                                <Card className="border-blue-300/50 bg-blue-50/30 dark:bg-blue-900/10 shrink-0">
                                    <CardHeader className="py-2">
                                        <CardTitle className="text-sm flex items-center gap-2 text-blue-600 dark:text-blue-400">
                                            <Wand2 className="w-4 h-4" />
                                            Refine with AI
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="py-0 pb-3 flex gap-2">
                                        <Input
                                            placeholder="e.g., 'Fix the date format', 'Remove empty rows'..."
                                            value={feedback}
                                            onChange={(e) => setFeedback(e.target.value)}
                                            onKeyDown={(e) => e.key === 'Enter' && handleRefine()}
                                            className="bg-background text-sm"
                                        />
                                        <Button size="sm" onClick={handleRefine} disabled={isRefining || !feedback.trim()}>
                                            {isRefining ? <Spinner className="w-4 h-4" /> : "Fix"}
                                        </Button>
                                    </CardContent>
                                </Card>

                                {/* Transform Code - Collapsible */}
                                <Collapsible open={isCodeExpanded} onOpenChange={setIsCodeExpanded} className="shrink-0">
                                    <Card>
                                        <CollapsibleTrigger className="w-full">
                                            <CardHeader className="py-3 cursor-pointer hover:bg-muted/30 transition-colors">
                                                <CardTitle className="text-sm flex items-center justify-between">
                                                    <span className="flex items-center gap-2">
                                                        <Code className="w-4 h-4" />
                                                        Transformation Code (Python)
                                                    </span>
                                                    <div className="flex items-center gap-2">
                                                        <Button size="sm" variant="outline" className="h-6 text-xs" onClick={(e) => { e.stopPropagation(); handlePreviewTransform(); }}>
                                                            {step === 'previewing' ? <Spinner className="w-3 h-3 mr-1" /> : <Play className="w-3 h-3 mr-1" />}
                                                            Run
                                                        </Button>
                                                        <ChevronDown className={cn("w-4 h-4 transition-transform", !isCodeExpanded && "-rotate-90")} />
                                                    </div>
                                                </CardTitle>
                                            </CardHeader>
                                        </CollapsibleTrigger>
                                        <CollapsibleContent>
                                            <CardContent className="py-0 pb-3">
                                                <Textarea
                                                    className="font-mono text-xs bg-slate-950 text-slate-50 min-h-[150px] resize-none"
                                                    value={editedCode}
                                                    onChange={(e) => setEditedCode(e.target.value)}
                                                />
                                            </CardContent>
                                        </CollapsibleContent>
                                    </Card>
                                </Collapsible>
                            </div>

                            {/* Right Panel: Data Previews */}
                            <div className="flex flex-col gap-3 overflow-y-auto pr-2">{/* Allow scrolling */}                             {/* Raw Data Preview */}
                                <Card className="shrink-0 overflow-hidden">
                                    <CardHeader className="py-2 shrink-0">
                                        <CardTitle className="text-sm flex items-center justify-between">
                                            <span className="flex items-center gap-2">
                                                <Database className="w-4 h-4 text-muted-foreground" />
                                                Raw Data (Before)
                                            </span>
                                            <Badge variant="outline" className="text-[10px]">First 20 rows</Badge>
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="py-0 pb-3">
                                        {rawDataError ? (
                                            <Alert variant="destructive">
                                                <AlertTitle className="text-sm">Failed to Load</AlertTitle>
                                                <AlertDescription className="text-xs">{rawDataError}</AlertDescription>
                                            </Alert>
                                        ) : rawData ? renderDataTable(rawData, "h-[250px]") : (
                                            <div className="h-[250px] flex items-center justify-center text-muted-foreground text-sm border rounded-md">
                                                <Spinner className="w-4 h-4 mr-2" /> Loading...
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>

                                {/* Arrow */}
                                <div className="flex items-center justify-center shrink-0">
                                    <div className="flex items-center gap-2 text-muted-foreground">
                                        <div className="h-px w-12 bg-border" />
                                        <ArrowRight className="w-4 h-4" />
                                        <span className="text-xs">Transformation</span>
                                        <ArrowRight className="w-4 h-4" />
                                        <div className="h-px w-12 bg-border" />
                                    </div>
                                </div>

                                {/* Transformed Data Preview */}
                                <Card className="shrink-0 overflow-hidden border-primary/30 bg-primary/5">
                                    <CardHeader className="py-2 shrink-0">
                                        <CardTitle className="text-sm flex items-center justify-between">
                                            <span className="flex items-center gap-2">
                                                <Eye className="w-4 h-4 text-primary" />
                                                Transformed Data (After)
                                            </span>
                                            <Badge variant="secondary" className="text-[10px]">First 20 rows</Badge>
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="py-0 pb-3">
                                        {previewError && (
                                            <Alert variant="destructive" className="mb-2">
                                                <AlertTitle className="text-sm">Preview Failed</AlertTitle>
                                                <AlertDescription className="text-xs">{previewError}</AlertDescription>
                                            </Alert>
                                        )}
                                        {previewData ? renderDataTable(previewData, "h-[250px]") : (
                                            <div className="h-[250px] flex items-center justify-center text-muted-foreground text-sm border rounded-md bg-muted/10">
                                                Click "Run" to preview transformation
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer - only show in review mode */}
                {mode === 'review' && (
                    <DialogFooter className="px-6 py-3 border-t shrink-0 flex items-center justify-between">
                        <Button variant="outline" onClick={onClose}>
                            Cancel
                        </Button>

                        <div className="flex items-center gap-4">
                            <RadioGroup value={saveMode} onValueChange={(v) => setSaveMode(v as 'replace' | 'new')} className="flex gap-4">
                                <div className="flex items-center space-x-2">
                                    <RadioGroupItem value="replace" id="replace" />
                                    <Label htmlFor="replace" className="text-sm cursor-pointer">Replace Table</Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <RadioGroupItem value="new" id="new" />
                                    <Label htmlFor="new" className="text-sm cursor-pointer">Save as New</Label>
                                </div>
                            </RadioGroup>
                            <Button onClick={handleSave} disabled={step === 'saving'} className="gap-2">
                                {step === 'saving' ? <Spinner className="w-4 h-4" /> : <Save className="w-4 h-4" />}
                                {saveMode === 'replace' ? 'Apply & Replace' : 'Save as New'}
                            </Button>
                        </div>
                    </DialogFooter>
                )}
            </DialogContent>
        </Dialog>
    );
}
