'use client';

import { useState } from 'react';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
import { Wand2, Play, Check, Save, X, AlertTriangle, ChevronLeft, ChevronRight } from 'lucide-react';
import { Spinner } from '@/components/ui/spinner';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { api } from '@/lib/api';
import { toast } from 'sonner';

interface AnalysisDialogProps {
    tableId: string;
    tableName: string;
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
}

interface AnalysisResult {
    summary: string;
    issues_found: string[];
    transform_code: string;
    needs_transform: boolean;
    validation_notes: string[];
    explanation: string;
    preview_data: any[]; // Small preview from analysis
    has_error: boolean;
}

export function AnalysisDialog({ tableId, tableName, isOpen, onClose, onSuccess }: AnalysisDialogProps) {
    // States
    const [step, setStep] = useState<'input' | 'analyzing' | 'review' | 'previewing' | 'saving'>('input');
    const [description, setDescription] = useState('');
    const [result, setResult] = useState<AnalysisResult | null>(null);
    const [editedCode, setEditedCode] = useState('');
    const [feedback, setFeedback] = useState('');
    const [isRefining, setIsRefining] = useState(false);

    // History State
    const [history, setHistory] = useState<AnalysisResult[]>([]);
    const [historyIndex, setHistoryIndex] = useState(0);

    // Preview Transform State
    const [previewData, setPreviewData] = useState<{ columns: string[], data: any[] } | null>(null);
    const [previewError, setPreviewError] = useState<string | null>(null);

    // Save Mode: 'replace' overwrites current table, 'new' creates a new table
    const [saveMode, setSaveMode] = useState<'replace' | 'new'>('replace');

    const updateCurrentResult = (newResult: AnalysisResult) => {
        setResult(newResult);
        setEditedCode(newResult.transform_code || '');
    };

    const handleHistoryNavigate = (direction: 'prev' | 'next') => {
        const newIndex = direction === 'prev'
            ? Math.max(0, historyIndex - 1)
            : Math.min(history.length - 1, historyIndex + 1);

        setHistoryIndex(newIndex);
        updateCurrentResult(history[newIndex]);
        setPreviewData(null); // Clear preview when switching versions
    };

    const handleAnalyze = async () => {
        setStep('analyzing');
        setPreviewData(null);
        setPreviewError(null);

        try {
            const res = await api.analyzeFile(tableId, description);
            const data = res.data;

            updateCurrentResult(data);
            setHistory([data]);
            setHistoryIndex(0);

            if (data.has_error) {
                toast.error("Analysis failed: " + data.explanation);
                setStep('input');
            } else {
                setStep('review');
            }
        } catch (error: any) {
            console.error("Analysis error:", error);
            toast.error("Failed to analyze file: " + (error.response?.data?.detail || error.message));
            setStep('input');
        }
    };

    const handlePreviewTransform = async () => {
        setStep('previewing');
        setPreviewError(null);
        try {
            const res = await api.previewTransform(tableId, editedCode);
            if (res.data.error) {
                setPreviewError(res.data.error);
            } else {
                setPreviewData({
                    columns: res.data.columns,
                    data: res.data.preview_data
                });
            }
        } catch (error: any) {
            setPreviewError(error.response?.data?.detail || error.message);
        } finally {
            setStep('review');
        }
    };

    const handleRefine = async () => {
        if (!feedback.trim()) return;
        setIsRefining(true);
        try {
            const res = await api.refineTransform(tableId, editedCode, feedback);
            const data = res.data;

            // Add to history
            const newHistory = [...history.slice(0, historyIndex + 1), data];
            setHistory(newHistory);
            setHistoryIndex(newHistory.length - 1);

            updateCurrentResult(data);
            setFeedback(''); // Clear feedback
            toast.success("Code refined by AI!");
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
            await api.confirmTransform(tableId, editedCode, undefined, replaceOriginal);
            toast.success(
                replaceOriginal
                    ? "Transformation applied and table updated!"
                    : "Transformation applied and saved as new table!"
            );
            onSuccess();
            onClose();
        } catch (error: any) {
            toast.error("Failed to save: " + (error.response?.data?.detail || error.message));
            setStep('review');
        }
    };

    // Reset state on close
    const handleOpenChange = (open: boolean) => {
        if (!open) {
            // Reset state
            setTimeout(() => {
                setStep('input');
                setDescription('');
                setResult(null);
                setEditedCode('');
                setPreviewData(null);
                setHistory([]);
                setSaveMode('replace');
                setHistoryIndex(0);
            }, 300);
            onClose();
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={handleOpenChange}>
            <DialogContent className="max-w-[90vw] h-[90vh] flex flex-col p-0 gap-0">
                <DialogHeader className="px-6 py-4 border-b flex flex-row items-center justify-between">
                    <div className="space-y-1.5">
                        <DialogTitle className="flex items-center gap-2">
                            <Wand2 className="w-5 h-5 text-primary" />
                            AI Data Analyst: {tableName}
                        </DialogTitle>
                        <DialogDescription>
                            Analyze data quality and confirm transformations.
                        </DialogDescription>
                    </div>

                    {(step === 'review' || step === 'previewing' || step === 'saving') && history.length > 1 && (
                        <div className="flex items-center gap-2 bg-muted/50 p-1.5 rounded-md text-sm border">
                            <span className="text-muted-foreground px-2">Version {historyIndex + 1} of {history.length}</span>
                            <div className="flex gap-1">
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-6 w-6"
                                            onClick={() => handleHistoryNavigate('prev')}
                                            disabled={historyIndex === 0}
                                        >
                                            <span className="sr-only">Previous</span>
                                            <ChevronLeft className="w-4 h-4" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p>Previous version</p>
                                    </TooltipContent>
                                </Tooltip>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-6 w-6"
                                            onClick={() => handleHistoryNavigate('next')}
                                            disabled={historyIndex === history.length - 1}
                                        >
                                            <span className="sr-only">Next</span>
                                            <ChevronRight className="w-4 h-4" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p>Next version</p>
                                    </TooltipContent>
                                </Tooltip>
                            </div>
                        </div>
                    )}
                </DialogHeader>

                <div className="flex-1 overflow-y-auto px-6 py-4">
                    {step === 'input' && (
                        <div className="space-y-4">
                            <div className="bg-muted/50 p-4 rounded-lg">
                                <h4 className="font-semibold mb-2">What happens next?</h4>
                                <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                                    <li>AI will scan the <strong>cached parquet file</strong>.</li>
                                    <li>It detects missing values, outliers, and type mismatches.</li>
                                    <li>It proposes Python code to clean the data.</li>
                                    <li>You can review, edit code, and preview changes before saving.</li>
                                </ul>
                            </div>

                            <div className="space-y-2">
                                <Label className="text-sm font-medium">
                                    Optional: Describe specific issues or cleaning rules
                                </Label>
                                <Textarea
                                    placeholder="e.g. Remove rows where 'Status' is empty, Convert 'Date' to datetime..."
                                    value={description}
                                    onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setDescription(e.target.value)}
                                    rows={4}
                                />
                            </div>
                        </div>
                    )}

                    {step === 'analyzing' && (
                        <div className="flex flex-col items-center justify-center py-12 space-y-4">
                            <Spinner className="size-12 text-primary" />
                            <p className="text-muted-foreground animate-pulse">Analyzing data patterns...</p>
                        </div>
                    )}

                    {(step === 'review' || step === 'previewing' || step === 'saving') && result && (
                        <div className="space-y-6">
                            {/* Summary Section */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <Alert variant={result.needs_transform ? "default" : "default"} className="bg-blue-50/10 border-blue-200/20">
                                    <AlertTitle className="text-blue-500 font-semibold mb-2">Analysis Summary</AlertTitle>
                                    <AlertDescription className="text-sm">
                                        {result.summary}
                                    </AlertDescription>
                                </Alert>

                                <div className="border rounded-md p-4 bg-muted/20">
                                    <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                                        <AlertTriangle className="w-4 h-4 text-amber-500" />
                                        Issues Detected
                                    </h4>
                                    {result.issues_found && result.issues_found.length > 0 ? (
                                        <ul className="text-sm space-y-1">
                                            {result.issues_found.map((issue, i) => (
                                                <li key={i} className="flex items-start gap-2">
                                                    <span className="text-muted-foreground">•</span>
                                                    <span>{issue}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    ) : (
                                        <p className="text-sm text-muted-foreground">No major issues found.</p>
                                    )}
                                </div>
                            </div>

                            {/* Refine Section */}
                            <div className="bg-blue-50/10 border border-blue-200/20 rounded-md p-4 space-y-2">
                                <h4 className="text-sm font-semibold flex items-center gap-2">
                                    <Wand2 className="w-4 h-4 text-blue-500" />
                                    Refine with AI
                                </h4>
                                <div className="flex gap-2">
                                    <Input
                                        placeholder="Describe what to fix (e.g. 'Fix the date format', 'Remove empty rows')..."
                                        value={feedback}
                                        onChange={(e) => setFeedback(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handleRefine()}
                                    />
                                    <Button onClick={handleRefine} disabled={isRefining || !feedback.trim()} size="sm">
                                        {isRefining ? <Spinner /> : "Fix Code"}
                                    </Button>
                                </div>
                            </div>

                            {/* Code Section */}
                            <div className="space-y-2">
                                <div className="flex items-center justify-between">
                                    <Label className="text-sm font-medium">Transformation Logic (Python)</Label>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handlePreviewTransform}
                                        disabled={step === 'previewing'}
                                    >
                                        {step === 'previewing' ? (
                                            <Spinner className="size-3" />
                                        ) : (
                                            <Play className="w-3 h-3 mr-2" />
                                        )}
                                        Run Preview
                                    </Button>
                                </div>
                                <Textarea
                                    className="font-mono text-xs bg-slate-950 text-slate-50 min-h-[150px]"
                                    value={editedCode}
                                    onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setEditedCode(e.target.value)}
                                />
                                <p className="text-xs text-muted-foreground">
                                    The variable <code>df</code> is your dataframe. Modify it in place or return a new one.
                                </p>
                            </div>

                            {/* Preview Section */}
                            {previewError && (
                                <Alert variant="destructive">
                                    <AlertTitle>Preview Failed</AlertTitle>
                                    <AlertDescription>{previewError}</AlertDescription>
                                </Alert>
                            )}

                            {previewData && (
                                <Card className="border-primary/20 bg-primary/5 mt-4">
                                    <CardHeader className="py-4 px-6">
                                        <div className="flex justify-between items-center">
                                            <h3 className="text-sm font-medium leading-none tracking-tight flex items-center gap-2">
                                                Preview Result
                                            </h3>
                                            <Badge variant="secondary" className="text-[10px] h-5 font-normal">
                                                First 20 rows
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
                                                                {previewData.columns.map((col) => (
                                                                    <TableHead key={col} className="bg-muted/50 px-4 py-2 whitespace-nowrap text-muted-foreground font-medium sticky top-0 z-10">{col}</TableHead>
                                                                ))}
                                                            </TableRow>
                                                        </TableHeader>
                                                        <TableBody>
                                                            {previewData.data.map((row, i) => (
                                                                <TableRow key={i} className="border-t border-muted/50 text-xs">
                                                                    {previewData.columns.map((col) => {
                                                                        const cellValue = String(row[col] ?? "");
                                                                        const isTruncated = cellValue.length > 60;
                                                                        return (
                                                                            <TableCell key={col} className="px-4 py-2 whitespace-nowrap border-r last:border-r-0">
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
                            )}
                        </div>
                    )}
                </div>

                <DialogFooter className="px-6 py-4 border-t bg-muted/20">
                    <Button variant="ghost" onClick={() => handleOpenChange(false)}>
                        Cancel
                    </Button>

                    {step === 'input' && (
                        <Button onClick={handleAnalyze} className="gap-2">
                            <Wand2 className="w-4 h-4" /> Analyze
                        </Button>
                    )}

                    {(step === 'review' || step === 'previewing' || step === 'saving') && (
                        <div className="flex items-center gap-4">
                            <RadioGroup
                                value={saveMode}
                                onValueChange={(v: string) => setSaveMode(v as 'replace' | 'new')}
                                className="flex gap-4"
                            >
                                <div className="flex items-center space-x-2">
                                    <RadioGroupItem value="replace" id="replace" />
                                    <Label htmlFor="replace" className="text-sm cursor-pointer">Replace Current Table</Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <RadioGroupItem value="new" id="new" />
                                    <Label htmlFor="new" className="text-sm cursor-pointer">Save as New Table</Label>
                                </div>
                            </RadioGroup>
                            <Button onClick={handleSave} disabled={step === 'saving'} className="gap-2">
                                {step === 'saving' ? (
                                    <Spinner />
                                ) : (
                                    <Save className="w-4 h-4" />
                                )}
                                {saveMode === 'replace' ? 'Apply & Replace' : 'Save as New'}
                            </Button>
                        </div>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
