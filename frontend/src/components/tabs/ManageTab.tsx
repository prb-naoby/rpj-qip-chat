'use client';

/**
 * Manage Tables Tab Component
 * View and manage cached data tables
 */
import { useState } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchTables, deleteTable, TableInfo } from '@/store/slices/tablesSlice';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Eye, Pencil, Download } from 'lucide-react';
import { Spinner } from '@/components/ui/spinner';
import { DataPreview } from '@/components/DataPreview';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import api from '@/lib/api';
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { toast } from 'sonner';

import { AnalysisDialog } from '@/components/analysis/AnalysisDialog';

interface DeleteTarget {
    cachePath: string;
    displayName: string;
}

interface AnalysisTarget {
    tableId: string;
    tableName: string;
}

interface EditTarget {
    cachePath: string;
    displayName: string;
    description: string;
}

import { RootState } from '@/store';

export default function ManageTab() {
    const dispatch = useAppDispatch();
    const { tables, isLoading } = useAppSelector((state: any) => state.tables); // Temporary fix, should use RootState properly but avoiding complex circular deps or type mismatches for now. Or check RootState definition.
    const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
    const [analysisTarget, setAnalysisTarget] = useState<AnalysisTarget | null>(null);
    const [editTarget, setEditTarget] = useState<EditTarget | null>(null);
    const [editDescription, setEditDescription] = useState('');
    const [isDeleting, setIsDeleting] = useState(false);
    const [isSavingDescription, setIsSavingDescription] = useState(false);
    const [selectedTableId, setSelectedTableId] = useState<string | null>(null);

    const handleRefresh = () => {
        dispatch(fetchTables());
    };

    const handleConfirmDelete = async () => {
        if (!deleteTarget) return;

        setIsDeleting(true);
        try {
            await dispatch(deleteTable(deleteTarget.cachePath)).unwrap();
            toast.success(`✅ Table "${deleteTarget.displayName}" deleted successfully`);
            setDeleteTarget(null);
        } catch (error: any) {
            toast.error(`Failed to delete: ${error}`);
        } finally {
            setIsDeleting(false);
        }
    };

    const handleAnalysisSuccess = () => {
        dispatch(fetchTables());
        setAnalysisTarget(null);
    };

    const handleEditClick = (table: TableInfo) => {
        setEditTarget({
            cachePath: table.cache_path,
            displayName: table.display_name,
            description: table.description || ''
        });
        setEditDescription(table.description || '');
    };

    const handleSaveDescription = async () => {
        if (!editTarget) return;

        setIsSavingDescription(true);
        try {
            await api.updateTableDescription(editTarget.cachePath, editDescription);
            toast.success(`✅ Deskripsi berhasil disimpan`);
            dispatch(fetchTables());
            setEditTarget(null);
        } catch (error: any) {
            toast.error(`Gagal menyimpan: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsSavingDescription(false);
        }
    };

    const formatSize = (mb: number) => {
        return mb.toFixed(2) + ' MB';
    };

    const formatDate = (dateStr: string) => {
        try {
            return new Date(dateStr).toLocaleString('id-ID');
        } catch {
            return dateStr;
        }
    };

    return (
        <>
            <Card className="bg-card border-border">
                <CardHeader className="pb-2">
                    <CardTitle className="text-lg text-card-foreground flex items-center justify-between">
                        <span>🛠️ Manage Tables</span>
                        <Button
                            onClick={handleRefresh}
                            disabled={isLoading}
                            size="sm"
                            className="active:scale-[0.98]"
                        >
                            {isLoading ? <><Spinner />Loading...</> : '🔄 Refresh'}
                        </Button>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {tables.length === 0 ? (
                        <div className="text-center py-8 text-muted-foreground">
                            <div className="text-4xl mb-4">📊</div>
                            <p>Belum ada tabel yang di-cache.</p>
                            <p className="text-sm">Upload file atau sync dari OneDrive untuk memulai.</p>
                        </div>
                    ) : (
                        <ScrollArea className="w-full h-[600px] border rounded-md">
                            <div className="min-w-[700px]">
                                <Table>
                                    <TableHeader className="bg-muted/50 sticky top-0 z-10">
                                        <TableRow className="border-border hover:bg-muted/50">
                                            <TableHead className="text-muted-foreground w-[40%]">Name</TableHead>
                                            <TableHead className="text-muted-foreground w-[10%]">Rows</TableHead>
                                            <TableHead className="text-muted-foreground w-[10%]">Cols</TableHead>
                                            <TableHead className="text-muted-foreground w-[10%]">Size</TableHead>
                                            <TableHead className="text-muted-foreground w-[15%]">Cached</TableHead>
                                            <TableHead className="text-muted-foreground text-right w-[15%]">Actions</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        <AnimatePresence>
                                            {tables.map((table: TableInfo, index: number) => (
                                                <motion.tr
                                                    key={table.cache_path}
                                                    initial={{ opacity: 0, y: 10 }}
                                                    animate={{ opacity: 1, y: 0 }}
                                                    exit={{ opacity: 0, x: -20 }}
                                                    transition={{ delay: index * 0.05, duration: 0.2 }}
                                                    className="border-border hover:bg-muted/50 transition-colors"
                                                >
                                                    <TableCell className="font-medium text-foreground">
                                                        <div className="max-w-[400px] font-medium break-words whitespace-normal">
                                                            {table.display_name}
                                                        </div>
                                                        {table.description && (
                                                            <Tooltip>
                                                                <TooltipTrigger asChild>
                                                                    <div className="text-xs text-muted-foreground truncate">
                                                                        {table.description}
                                                                    </div>
                                                                </TooltipTrigger>
                                                                <TooltipContent className="max-w-md">
                                                                    <p>{table.description}</p>
                                                                </TooltipContent>
                                                            </Tooltip>
                                                        )}
                                                    </TableCell>
                                                    <TableCell className="text-muted-foreground">
                                                        {table.n_rows.toLocaleString()}
                                                    </TableCell>
                                                    <TableCell className="text-muted-foreground">
                                                        {table.n_cols}
                                                    </TableCell>
                                                    <TableCell className="text-muted-foreground">
                                                        {formatSize(table.file_size_mb)}
                                                    </TableCell>
                                                    <TableCell className="text-muted-foreground">
                                                        {formatDate(table.cached_at)}
                                                    </TableCell>
                                                    <TableCell className="text-right flex justify-end gap-1">
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon-sm"
                                                                    onClick={() => setSelectedTableId(
                                                                        selectedTableId === table.cache_path ? null : table.cache_path
                                                                    )}
                                                                    className={selectedTableId === table.cache_path
                                                                        ? "text-primary bg-primary/10"
                                                                        : "text-muted-foreground hover:text-foreground"
                                                                    }
                                                                    aria-label="Preview table"
                                                                >
                                                                    <Eye className="h-4 w-4" />
                                                                </Button>
                                                            </TooltipTrigger>
                                                            <TooltipContent>
                                                                <p>Preview Data</p>
                                                            </TooltipContent>
                                                        </Tooltip>

                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon-sm"
                                                                    onClick={() => handleEditClick(table)}
                                                                    className="text-muted-foreground hover:text-foreground hover:bg-muted"
                                                                    aria-label="Edit description"
                                                                >
                                                                    <Pencil className="h-4 w-4" />
                                                                </Button>
                                                            </TooltipTrigger>
                                                            <TooltipContent>
                                                                <p>Edit Description</p>
                                                            </TooltipContent>
                                                        </Tooltip>

                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon-sm"
                                                                    onClick={() => {
                                                                        const filename = table.display_name.replace(/[^a-zA-Z0-9]/g, '_') + '.csv';
                                                                        api.downloadTableCsv(table.cache_path, filename);
                                                                        toast.success('Download started!');
                                                                    }}
                                                                    className="text-green-500 hover:text-green-600 hover:bg-green-500/10"
                                                                    aria-label="Download as CSV"
                                                                >
                                                                    <Download className="h-4 w-4" />
                                                                </Button>
                                                            </TooltipTrigger>
                                                            <TooltipContent>
                                                                <p>Download as CSV</p>
                                                            </TooltipContent>
                                                        </Tooltip>

                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon-sm"
                                                                    onClick={() => setAnalysisTarget({
                                                                        tableId: table.cache_path,
                                                                        tableName: table.display_name
                                                                    })}
                                                                    className="text-blue-500 hover:text-blue-600 hover:bg-blue-500/10"
                                                                    aria-label="Analyze & Transform"
                                                                >
                                                                    ✨
                                                                </Button>
                                                            </TooltipTrigger>
                                                            <TooltipContent>
                                                                <p>Analyze & Transform Data</p>
                                                            </TooltipContent>
                                                        </Tooltip>

                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon-sm"
                                                                    onClick={() => setDeleteTarget({
                                                                        cachePath: table.cache_path,
                                                                        displayName: table.display_name
                                                                    })}
                                                                    className="text-destructive hover:text-destructive hover:bg-destructive/10 active:scale-[0.95]"
                                                                    aria-label={`Hapus tabel ${table.display_name}`}
                                                                >
                                                                    🗑️
                                                                </Button>
                                                            </TooltipTrigger>
                                                            <TooltipContent>
                                                                <p>Delete this table</p>
                                                            </TooltipContent>
                                                        </Tooltip>
                                                    </TableCell>
                                                </motion.tr>
                                            ))}
                                        </AnimatePresence>
                                    </TableBody>
                                </Table>
                            </div>
                            <ScrollBar orientation="horizontal" />
                            <ScrollBar orientation="vertical" />
                        </ScrollArea>
                    )}
                </CardContent>
            </Card>

            <DataPreview tableId={selectedTableId} title="Table Preview" />

            {/* Analysis Dialog */}
            {
                analysisTarget && (
                    <AnalysisDialog
                        tableId={analysisTarget.tableId}
                        tableName={analysisTarget.tableName}
                        isOpen={!!analysisTarget}
                        onClose={() => setAnalysisTarget(null)}
                        onSuccess={handleAnalysisSuccess}
                    />
                )
            }

            {/* Delete Confirmation Dialog */}
            <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
                <AlertDialogContent className="bg-card border-border">
                    <AlertDialogHeader>
                        <AlertDialogTitle className="text-card-foreground">
                            🗑️ Delete Table
                        </AlertDialogTitle>
                        <AlertDialogDescription className="text-muted-foreground">
                            Are you sure you want to delete table <strong className="text-foreground">"{deleteTarget?.displayName}"</strong>?
                            This action cannot be undone.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel
                            className="border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                            disabled={isDeleting}
                        >
                            Cancel
                        </AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleConfirmDelete}
                            disabled={isDeleting}
                            className="bg-destructive hover:bg-destructive/90 text-destructive-foreground active:scale-[0.98]"
                        >
                            {isDeleting ? 'Deleting...' : 'Delete'}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            {/* Edit Description Dialog */}
            <Dialog open={!!editTarget} onOpenChange={(open) => !open && setEditTarget(null)}>
                <DialogContent className="bg-card border-border">
                    <DialogHeader>
                        <DialogTitle className="text-card-foreground">
                            ✏️ Edit Description: {editTarget?.displayName}
                        </DialogTitle>
                    </DialogHeader>
                    <div className="py-4">
                        <Textarea
                            placeholder="Add a description to help AI understand this data..."
                            value={editDescription}
                            onChange={(e) => setEditDescription(e.target.value)}
                            className="min-h-[100px] bg-background border-input"
                        />
                        <p className="text-xs text-muted-foreground mt-2">
                            A good description helps AI provide more accurate answers when querying this data.
                        </p>
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setEditTarget(null)}
                            disabled={isSavingDescription}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={handleSaveDescription}
                            disabled={isSavingDescription}
                        >
                            {isSavingDescription ? <>
                                <Spinner />Saving...
                            </> : '💾 Save'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}

