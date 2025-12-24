import React from 'react';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { AlertCircle, CheckCircle2, Info, AlertTriangle, Terminal } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";


interface UIComponent {
    type: 'table' | 'stat' | 'text' | 'json' | 'alert' | 'clarification';
    [key: string]: any;
}

interface AnalysisResultProps {
    components: UIComponent[];
    onAction?: (action: string, data: any) => void;
}

export function AnalysisResult({ components, onAction }: AnalysisResultProps) {
    if (!components || components.length === 0) return null;

    return (
        <div className="space-y-3">
            {components.map((component, index) => (
                <div key={index} className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                    {renderNativeComponent(component, onAction)}
                </div>
            ))}
        </div>
    );
}

function renderNativeComponent(component: UIComponent, onAction?: (action: string, data: any) => void) {
    switch (component.type) {
        case 'clarification':
            return <NativeClarification options={component.options} onSelect={(option) => onAction?.('select_table', option)} />;

        case 'table':
            return <NativeTable data={component.data} columns={component.columns} totalRows={component.total_rows} label={component.label} />;

        case 'stat':
            return <NativeStat value={component.value} label={component.label} delta={component.delta} />;

        case 'text':
            return <div className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">{component.content}</div>;

        case 'json':
            return <NativeJson data={component.data} label={component.label} />;

        case 'alert':
            return <NativeAlert variant={component.variant} title={component.title} content={component.content} />;

        default:
            console.warn("Unknown component type:", component.type);
            return null;
    }
}

function NativeTable({ data, columns, totalRows, label }: { data: any[], columns?: string[], totalRows?: number, label?: string }) {
    if (!data || data.length === 0) return <div className="text-muted-foreground text-sm italic">No data to display</div>;

    const cols = columns || Object.keys(data[0]);

    return (
        <Card className="w-full my-4 border-primary/20 bg-primary/5">
            {label && (
                <CardHeader className="py-4 px-6">
                    <div className="flex justify-between items-center">
                        <h3 className="text-sm font-medium leading-none tracking-tight flex items-center gap-2">
                            <span className="text-muted-foreground scale-75">📊</span> {label}
                        </h3>
                        {totalRows && <Badge variant="secondary" className="text-[10px] h-5 font-normal">{totalRows} rows</Badge>}
                    </div>
                </CardHeader>
            )}
            <CardContent className={label ? "p-6 pt-0" : "p-4"}>
                <div className="rounded-md border bg-background">
                    <ScrollArea className="h-[400px] w-full rounded-md">
                        <div className="min-w-max p-1">
                            <Table>
                                <TableHeader>
                                    <TableRow className="hover:bg-transparent">
                                        {cols.map((col) => (
                                            <TableHead key={col} className="bg-muted/50 px-3 py-2 h-9 font-semibold text-xs uppercase tracking-wider text-muted-foreground whitespace-nowrap sticky top-0 z-10">
                                                {col}
                                            </TableHead>
                                        ))}
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.map((row, i) => (
                                        <TableRow key={i} className="hover:bg-muted/50 transition-colors">
                                            {cols.map((col) => {
                                                const cellValue = formatValue(row[col]);
                                                const isTruncated = cellValue.length > 50;
                                                return (
                                                    <TableCell key={`${i}-${col}`} className="px-3 py-2 border-r last:border-r-0 border-border/50 text-sm tabular-nums whitespace-nowrap">
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
                        <ScrollBar orientation="vertical" />
                    </ScrollArea>
                </div>
            </CardContent>
            {totalRows && totalRows > data.length && (
                <div className="p-2 text-xs text-center text-muted-foreground bg-muted/20 border-t border-border/40 rounded-b-lg">
                    Showing top {data.length} of {totalRows} rows
                </div>
            )}
        </Card>
    );
}

function NativeStat({ value, label, delta }: { value: string | number, label: string, delta?: string }) {
    return (
        <div className="w-fit min-w-[180px] rounded-lg border border-border/40 bg-muted/20 p-4">
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
                {label}
            </div>
            <div className="text-2xl font-bold tracking-tight text-foreground">{formatValue(value)}</div>
            {delta && (
                <p className={`text-xs mt-1 font-medium ${delta.startsWith('-') ? 'text-destructive' : 'text-green-500'} flex items-center`}>
                    {delta.startsWith('-') ? '↓ ' : '↑ '}{delta}
                </p>
            )}
        </div>
    );
}

function NativeJson({ data, label }: { data: any, label?: string }) {
    // If data is an array of simple values, show as badges
    if (Array.isArray(data) && data.every(item => typeof item === 'string' || typeof item === 'number')) {
        return (
            <div className="space-y-2">
                {label && (
                    <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        {label}
                    </div>
                )}
                <div className="flex flex-wrap gap-2">
                    {data.map((item, idx) => (
                        <Badge key={idx} variant="secondary" className="text-sm font-normal">
                            {String(item)}
                        </Badge>
                    ))}
                </div>
            </div>
        );
    }

    // For complex objects, show in a collapsible code view
    return (
        <Collapsible className="w-full">
            <CollapsibleTrigger className="flex items-center gap-2 text-xs font-medium text-muted-foreground hover:text-primary transition-colors py-1">
                <Terminal className="w-3 h-3" />
                <span>{label || 'Raw Data'}</span>
            </CollapsibleTrigger>
            <CollapsibleContent>
                <ScrollArea className="max-h-[200px] w-full mt-2">
                    <pre className="p-3 text-xs font-mono text-muted-foreground bg-muted/30 rounded-lg border border-border/40 whitespace-pre-wrap">
                        {JSON.stringify(data, null, 2)}
                    </pre>
                </ScrollArea>
            </CollapsibleContent>
        </Collapsible>
    );
}

function NativeAlert({ variant, title, content }: { variant: 'success' | 'warning' | 'error' | 'info', title?: string, content: string }) {
    const outputVariant = variant === 'error' ? 'destructive' : 'default'; // Alert component only has standard variants
    const Icon = {
        success: CheckCircle2,
        warning: AlertTriangle,
        error: AlertCircle,
        info: Info
    }[variant] || Info;

    const bgClass = {
        success: 'bg-green-500/10 text-green-600 border-green-500/20',
        warning: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
        error: 'bg-destructive/10 text-destructive border-destructive/20',
        info: 'bg-blue-500/10 text-blue-600 border-blue-500/20'
    }[variant] || '';

    return (
        <Alert variant={outputVariant} className={`${outputVariant === 'default' ? bgClass : ''} border`}>
            <Icon className="h-4 w-4" />
            {title && <AlertTitle>{title}</AlertTitle>}
            <AlertDescription>{content}</AlertDescription>
        </Alert>
    );
}

function NativeClarification({ options, onSelect }: { options: any[], onSelect: (option: any) => void }) {
    // Safety check: ensure options is an array
    const safeOptions = Array.isArray(options) ? options : [];

    if (safeOptions.length === 0) {
        return null;
    }

    return (
        <div className="flex flex-col gap-2">
            {safeOptions.map((opt: any) => (
                <Button
                    key={opt.cache_path}
                    variant="outline"
                    className="justify-start h-auto p-3 text-left whitespace-normal hover:bg-primary/5 hover:text-primary transition-colors border-dashed hover:border-solid w-full"
                    onClick={() => onSelect(opt)}
                >
                    <div className="flex flex-col items-start gap-1 w-full">
                        <span className="font-semibold text-sm flex items-center gap-2">
                            📊 {opt.display_name}
                            <Badge variant="secondary" className="text-[10px] h-5">{Number(opt.score).toFixed(1)} score</Badge>
                        </span>
                        {opt.description && <span className="text-xs text-muted-foreground line-clamp-2">{opt.description}</span>}
                        <span className="text-xs text-muted-foreground opacity-70">{opt.n_rows?.toLocaleString() || 0} rows</span>
                    </div>
                </Button>
            ))}
        </div>
    )
}

function formatValue(val: any): string {
    if (val === null || val === undefined) return '-';
    if (typeof val === 'number') {
        // Format large numbers
        if (val > 10000) return val.toLocaleString('id-ID'); // Indonesian locale for readability
        // Limit decimals
        if (!Number.isInteger(val)) return Number(val.toFixed(2)).toString();
    }
    if (typeof val === 'object') return JSON.stringify(val);
    return String(val);
}
