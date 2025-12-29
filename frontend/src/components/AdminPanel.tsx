'use client';

/**
 * Admin Panel Component
 * User management dashboard for admins
 * - View all users
 * - Approve/reject pending registrations
 * - Create/delete users
 */
import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { Spinner } from '@/components/ui/spinner';
import { UserPlus, Trash2, CheckCircle, XCircle, RefreshCw, Users, Clock, Shield, Database } from 'lucide-react';
import { useUserJobs } from '@/hooks/useUserJobs';
import { JobStatusList } from '@/components/JobStatusList';
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

interface User {
    id: number;
    username: string;
    role: string;
    display_name: string | null;
    created_at: string;
    requested_at?: string;
}

interface PendingUser {
    id: number;
    username: string;
    email: string | null;
    requested_at: string;
    status: string;
}

export default function AdminPanel() {
    // Active users state
    const [users, setUsers] = useState<User[]>([]);
    const [isLoadingUsers, setIsLoadingUsers] = useState(false);

    // Pending users state
    const [pendingUsers, setPendingUsers] = useState<PendingUser[]>([]);
    const [isLoadingPending, setIsLoadingPending] = useState(false);

    // Job polling
    const { jobs, isLoading: isJobsLoading, refresh: refreshJobs } = useUserJobs();
    const [isIngesting, setIsIngesting] = useState(false);

    // Create user form state
    const [newUsername, setNewUsername] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [newRole, setNewRole] = useState('user');
    const [newDisplayName, setNewDisplayName] = useState('');
    const [isCreating, setIsCreating] = useState(false);

    // Action states
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const [confirmAction, setConfirmAction] = useState<{ type: 'delete' | 'reject', id?: number, username: string } | null>(null);

    useEffect(() => {
        loadUsers();
        loadPendingUsers();
    }, []);

    const loadUsers = async () => {
        setIsLoadingUsers(true);
        try {
            const response = await api.adminListUsers();
            setUsers(response.data);
        } catch (error: any) {
            toast.error(`Failed to load users: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsLoadingUsers(false);
        }
    };

    const loadPendingUsers = async () => {
        setIsLoadingPending(true);
        try {
            const response = await api.adminListPendingUsers();
            setPendingUsers(response.data);
        } catch (error: any) {
            toast.error(`Failed to load pending users: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsLoadingPending(false);
        }
    };

    const handleCreateUser = async () => {
        if (!newUsername || !newPassword) {
            toast.error('Username and password are required');
            return;
        }

        setIsCreating(true);
        try {
            await api.adminCreateUser(newUsername, newPassword, newRole, newDisplayName || undefined);
            toast.success(`User "${newUsername}" created successfully`);
            setNewUsername('');
            setNewPassword('');
            setNewRole('user');
            setNewDisplayName('');
            loadUsers();
        } catch (error: any) {
            toast.error(`Failed to create user: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsCreating(false);
        }
    };

    const handleDeleteUser = (username: string) => {
        setConfirmAction({ type: 'delete', username });
    };

    const handleRejectUser = (userId: number, username: string) => {
        setConfirmAction({ type: 'reject', id: userId, username });
    };

    const executeConfirmAction = async () => {
        if (!confirmAction) return;

        if (confirmAction.type === 'delete') {
            setActionLoading(`delete-${confirmAction.username}`);
            try {
                await api.adminDeleteUser(confirmAction.username);
                toast.success(`User "${confirmAction.username}" deleted`);
                loadUsers();
            } catch (error: any) {
                toast.error(`Failed to delete user: ${error.response?.data?.detail || error.message}`);
            } finally {
                setActionLoading(null);
                setConfirmAction(null);
            }
        } else if (confirmAction.type === 'reject') {
            if (!confirmAction.id) return;
            setActionLoading(`reject-${confirmAction.id}`);
            try {
                await api.adminRejectUser(confirmAction.id);
                toast.success(`User "${confirmAction.username}" rejected`);
                loadPendingUsers();
            } catch (error: any) {
                toast.error(`Failed to reject user: ${error.response?.data?.detail || error.message}`);
            } finally {
                setActionLoading(null);
                setConfirmAction(null);
            }
        }
    };

    const handleApproveUser = async (userId: number, username: string) => {
        setActionLoading(`approve-${userId}`);
        try {
            await api.adminApproveUser(userId);
            toast.success(`User "${username}" approved!`);
            loadPendingUsers();
            loadUsers();
        } catch (error: any) {
            toast.error(`Failed to approve user: ${error.response?.data?.detail || error.message}`);
        } finally {
            setActionLoading(null);
        }
    };

    const formatDate = (dateStr: string | null | undefined) => {
        if (!dateStr) return '—';
        try {
            return new Date(dateStr).toLocaleString('id-ID', {
                dateStyle: 'medium',
                timeStyle: 'short',
                timeZone: 'Asia/Jakarta'
            });
        } catch {
            return dateStr;
        }
    };

    const getRoleBadge = (role: string) => {
        switch (role) {
            case 'admin':
                return <Badge variant="default" className="bg-purple-600">Admin</Badge>;
            case 'user':
                return <Badge variant="secondary">User</Badge>;
            default:
                return <Badge variant="outline">{role}</Badge>;
        }
    };

    const handleIngest = async (dryRun: boolean) => {
        setIsIngesting(true);
        try {
            await api.ingestAllDocuments(dryRun);
            toast.success(dryRun ? 'Dry run started' : 'Ingestion started');
        } catch (error: any) {
            toast.error(`Failed to start ingestion: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsIngesting(false);
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    <Shield className="w-6 h-6" />
                    Admin Panel
                </h1>
                <Button variant="outline" onClick={() => { loadUsers(); loadPendingUsers(); }} className="gap-2">
                    <RefreshCw className="w-4 h-4" />
                    Refresh
                </Button>
            </div>

            <Tabs defaultValue="users" className="w-full">
                <TabsList className="grid w-full grid-cols-4">
                    <TabsTrigger value="users" className="gap-2">
                        <Users className="w-4 h-4" />
                        Users ({users.length})
                    </TabsTrigger>
                    <TabsTrigger value="pending" className="gap-2">
                        <Clock className="w-4 h-4" />
                        Pending ({pendingUsers.length})
                        {pendingUsers.length > 0 && (
                            <Badge variant="destructive" className="ml-1 h-5 px-1.5">{pendingUsers.length}</Badge>
                        )}
                    </TabsTrigger>
                    <TabsTrigger value="create" className="gap-2">
                        <UserPlus className="w-4 h-4" />
                        Create User
                    </TabsTrigger>
                    <TabsTrigger value="ingestion" className="gap-2">
                        <Database className="w-4 h-4" />
                        Ingestion
                    </TabsTrigger>
                </TabsList>

                {/* Active Users Tab */}
                <TabsContent value="users">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Active Users</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {isLoadingUsers ? (
                                <div className="flex justify-center py-8">
                                    <Spinner />
                                </div>
                            ) : users.length === 0 ? (
                                <p className="text-muted-foreground text-center py-8">No users found</p>
                            ) : (
                                <ScrollArea className="h-[400px] border rounded-md">
                                    <Table>
                                        <TableHeader className="bg-muted/50 sticky top-0 z-10">
                                            <TableRow>
                                                <TableHead>Username</TableHead>
                                                <TableHead>Display Name</TableHead>
                                                <TableHead>Role</TableHead>
                                                <TableHead>Created</TableHead>
                                                <TableHead className="text-right">Actions</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {users.map((user) => (
                                                <TableRow key={user.id}>
                                                    <TableCell className="font-medium">{user.username}</TableCell>
                                                    <TableCell>{user.display_name || '—'}</TableCell>
                                                    <TableCell>{getRoleBadge(user.role)}</TableCell>
                                                    <TableCell className="text-sm text-muted-foreground">
                                                        {formatDate(user.created_at)}
                                                    </TableCell>
                                                    <TableCell className="text-right">
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() => handleDeleteUser(user.username)}
                                                            disabled={actionLoading === `delete-${user.username}` || user.role === 'admin'}
                                                            className="text-destructive hover:text-destructive hover:bg-destructive/10"
                                                        >
                                                            {actionLoading === `delete-${user.username}` ? (
                                                                <Spinner />
                                                            ) : (
                                                                <Trash2 className="w-4 h-4" />
                                                            )}
                                                        </Button>
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </ScrollArea>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Pending Users Tab */}
                <TabsContent value="pending">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Pending Registrations</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {isLoadingPending ? (
                                <div className="flex justify-center py-8">
                                    <Spinner />
                                </div>
                            ) : pendingUsers.length === 0 ? (
                                <Alert>
                                    <CheckCircle className="h-4 w-4" />
                                    <AlertTitle>All Clear!</AlertTitle>
                                    <AlertDescription>
                                        No pending registration requests.
                                    </AlertDescription>
                                </Alert>
                            ) : (
                                <ScrollArea className="h-[400px] border rounded-md">
                                    <Table>
                                        <TableHeader className="bg-muted/50 sticky top-0 z-10">
                                            <TableRow>
                                                <TableHead>Username</TableHead>
                                                <TableHead>Email</TableHead>
                                                <TableHead>Requested</TableHead>
                                                <TableHead className="text-right">Actions</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {pendingUsers.map((user) => (
                                                <TableRow key={user.id}>
                                                    <TableCell className="font-medium">{user.username}</TableCell>
                                                    <TableCell>{user.email || '—'}</TableCell>
                                                    <TableCell className="text-sm text-muted-foreground">
                                                        {formatDate(user.requested_at)}
                                                    </TableCell>
                                                    <TableCell className="text-right space-x-2">
                                                        <Button
                                                            variant="default"
                                                            size="sm"
                                                            onClick={() => handleApproveUser(user.id, user.username)}
                                                            disabled={actionLoading === `approve-${user.id}`}
                                                            className="gap-1 bg-green-600 hover:bg-green-700"
                                                        >
                                                            {actionLoading === `approve-${user.id}` ? (
                                                                <Spinner />
                                                            ) : (
                                                                <>
                                                                    <CheckCircle className="w-4 h-4" />
                                                                    Approve
                                                                </>
                                                            )}
                                                        </Button>
                                                        <Button
                                                            variant="destructive"
                                                            size="sm"
                                                            onClick={() => handleRejectUser(user.id, user.username)}
                                                            disabled={actionLoading === `reject-${user.id}`}
                                                            className="gap-1"
                                                        >
                                                            {actionLoading === `reject-${user.id}` ? (
                                                                <Spinner />
                                                            ) : (
                                                                <>
                                                                    <XCircle className="w-4 h-4" />
                                                                    Reject
                                                                </>
                                                            )}
                                                        </Button>
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </ScrollArea>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Create User Tab */}
                <TabsContent value="create">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Create New User</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="new-username">Username *</Label>
                                    <Input
                                        id="new-username"
                                        value={newUsername}
                                        onChange={(e) => setNewUsername(e.target.value)}
                                        placeholder="Enter username"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="new-password">Password *</Label>
                                    <Input
                                        id="new-password"
                                        type="password"
                                        value={newPassword}
                                        onChange={(e) => setNewPassword(e.target.value)}
                                        placeholder="Enter password"
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="new-display-name">Display Name</Label>
                                    <Input
                                        id="new-display-name"
                                        value={newDisplayName}
                                        onChange={(e) => setNewDisplayName(e.target.value)}
                                        placeholder="Optional display name"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="new-role">Role</Label>
                                    <Select value={newRole} onValueChange={setNewRole}>
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="user">User</SelectItem>
                                            <SelectItem value="admin">Admin</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>
                            <Button
                                onClick={handleCreateUser}
                                disabled={isCreating || !newUsername || !newPassword}
                                className="gap-2"
                            >
                                {isCreating ? (
                                    <>
                                        <Spinner />
                                        Creating...
                                    </>
                                ) : (
                                    <>
                                        <UserPlus className="w-4 h-4" />
                                        Create User
                                    </>
                                )}
                            </Button>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Ingestion Tab */}
                <TabsContent value="ingestion">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Document Ingestion</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="flex flex-col gap-4">
                                <Alert>
                                    <Database className="h-4 w-4" />
                                    <AlertTitle>Ingestion Control</AlertTitle>
                                    <AlertDescription>
                                        Trigger a full re-ingestion of all documents. This runs as a background job.
                                    </AlertDescription>
                                </Alert>
                                <div className="flex gap-4">
                                    <Button
                                        onClick={() => handleIngest(true)}
                                        variant="outline"
                                        disabled={isIngesting}
                                    >
                                        Start Dry Run
                                    </Button>
                                    <Button
                                        onClick={() => handleIngest(false)}
                                        variant="default"
                                        disabled={isIngesting}
                                        className="bg-purple-600 hover:bg-purple-700"
                                    >
                                        Start Full Ingestion
                                    </Button>
                                </div>
                            </div>

                            <JobStatusList
                                jobs={jobs}
                                isLoading={isJobsLoading}
                                title="Active Ingestion Jobs"
                                typeFilter={['ingest', 'ingest_dry_run']}
                                onJobsChange={refreshJobs}
                            />
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            <AlertDialog open={!!confirmAction} onOpenChange={(open) => !open && setConfirmAction(null)}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                        <AlertDialogDescription>
                            {confirmAction?.type === 'delete'
                                ? `This will permanently delete user "${confirmAction.username}". This action cannot be undone.`
                                : `This will reject the registration for "${confirmAction?.username}".`
                            }
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={executeConfirmAction}
                            className={confirmAction?.type === 'delete' || confirmAction?.type === 'reject' ? "bg-destructive text-destructive-foreground hover:bg-destructive/90" : ""}
                        >
                            {confirmAction?.type === 'delete' ? 'Delete' : 'Reject'}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
