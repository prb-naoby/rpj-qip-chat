import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Spinner } from "@/components/ui/spinner";
import { Badge } from "@/components/ui/badge";
import { AlertCircle } from "lucide-react";

interface DataPreviewProps {
    tableId: string | null;
    title?: string;
}

interface PreviewData {
    columns: string[];
    data: any[];
    total_rows: number;
}

export function DataPreview({ tableId, title = "Data Preview" }: DataPreviewProps) {
    const [preview, setPreview] = useState<PreviewData | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!tableId) {
            setPreview(null);
            return;
        }

        const fetchPreview = async () => {
            setIsLoading(true);
            setError(null);
            try {
                const response = await api.getTablePreview(tableId);
                setPreview(response.data);
            } catch (err: any) {
                console.error("Failed to load preview:", err);
                setError(err.response?.data?.detail || "Failed to load data preview");
            } finally {
                setIsLoading(false);
            }
        };

        fetchPreview();
    }, [tableId]);

    if (!tableId) return null;

    return (
        <AnimatePresence mode="wait">
            {error && (
                <motion.div
                    key="error"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.2 }}
                >
                    <Alert variant="destructive" className="mt-4">
                        <AlertCircle className="h-4 w-4" />
                        <AlertTitle>Error</AlertTitle>
                        <AlertDescription>{error}</AlertDescription>
                    </Alert>
                </motion.div>
            )}

            {isLoading && (
                <motion.div
                    key="loading"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                >
                    <Card className="mt-4">
                        <CardHeader>
                            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                                <Spinner />
                                Loading preview...
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-2">
                                <Skeleton className="h-8 w-full" />
                                <Skeleton className="h-8 w-full" />
                                <Skeleton className="h-8 w-full" />
                            </div>
                        </CardContent>
                    </Card>
                </motion.div>
            )}

            {!isLoading && !error && preview && (
                <motion.div
                    key="preview"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.3 }}
                >
                    <Card className="mt-4 border-primary/20 bg-primary/5">
                        <CardHeader className="py-4 px-6">
                            <div className="flex justify-between items-center">
                                <h3 className="text-sm font-medium leading-none tracking-tight flex items-center gap-2">
                                    {title}
                                </h3>
                                <Badge variant="secondary" className="text-[10px] h-5 font-normal">
                                    {preview.data.length} rows shown
                                </Badge>
                            </div>
                        </CardHeader>
                        <CardContent className="p-6 pt-0">
                            <div className="rounded-md border bg-background">
                                <ScrollArea className="h-[400px] w-full rounded-md">
                                    <div className="min-w-max p-1"> {/* Wrapper to ensure table expands */}
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    {preview.columns.map((col) => (
                                                        <TableHead key={col} className="bg-muted/50 px-3 py-2 font-semibold text-xs whitespace-nowrap sticky top-0 z-10">
                                                            {col}
                                                        </TableHead>
                                                    ))}
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {preview.data.map((row, i) => (
                                                    <TableRow key={i} className="hover:bg-muted/50 text-xs">
                                                        {preview.columns.map((col) => {
                                                            const cellValue = String(row[col] ?? "");
                                                            const isTruncated = cellValue.length > 60;
                                                            return (
                                                                <TableCell key={`${i}-${col}`} className="px-3 py-1.5 border-r last:border-r-0 whitespace-nowrap">
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
                </motion.div>
            )}
        </AnimatePresence>
    );
}
