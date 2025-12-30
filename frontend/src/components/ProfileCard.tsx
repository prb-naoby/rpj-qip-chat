'use client';

/**
 * ProfileCard Component
 * Slim profile display with floating dropdown menu for settings
 * Pattern: Like exim-chat's nav-user.tsx
 */
import { useState } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { changePassword, fetchCurrentUser } from '@/store/slices/authSlice';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { MoreHorizontal, UserPen, KeyRound, LogOut } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from '@/components/ui/dialog';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface ProfileCardProps {
    onLogout: () => void;
}

export default function ProfileCard({ onLogout }: ProfileCardProps) {
    const dispatch = useAppDispatch();
    const { user, isLoading } = useAppSelector((state) => state.auth);

    // State for change display name dialog
    const [newDisplayName, setNewDisplayName] = useState('');
    const [isUpdatingName, setIsUpdatingName] = useState(false);
    const [isNameDialogOpen, setIsNameDialogOpen] = useState(false);

    // State for change password dialog
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [isPasswordDialogOpen, setIsPasswordDialogOpen] = useState(false);

    // Use display_name if available, otherwise fallback to username
    const displayName = user?.display_name || user?.username || 'User';

    // Handle display name update
    const handleUpdateDisplayName = async () => {
        if (!newDisplayName.trim()) {
            toast.error('Display name cannot be empty');
            return;
        }

        setIsUpdatingName(true);
        try {
            await api.updateProfile(newDisplayName.trim());
            toast.success('✅ Display name updated successfully');
            dispatch(fetchCurrentUser());
            setIsNameDialogOpen(false);
            setNewDisplayName('');
        } catch (error: any) {
            toast.error(`Failed to update: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsUpdatingName(false);
        }
    };

    // Handle password change
    const handleChangePassword = async () => {
        if (!currentPassword || !newPassword) {
            toast.error('All fields are required');
            return;
        }

        if (newPassword !== confirmPassword) {
            toast.error('New passwords do not match');
            return;
        }

        if (newPassword.length < 6) {
            toast.error('Password must be at least 6 characters');
            return;
        }

        try {
            await dispatch(changePassword({
                current_password: currentPassword,
                new_password: newPassword,
            })).unwrap();

            toast.success('✅ Password changed successfully');
            setIsPasswordDialogOpen(false);
            setCurrentPassword('');
            setNewPassword('');
            setConfirmPassword('');
        } catch (error: any) {
            toast.error(`Failed to change password: ${error}`);
        }
    };

    const resetPasswordForm = () => {
        setCurrentPassword('');
        setNewPassword('');
        setConfirmPassword('');
    };

    const resetNameForm = () => {
        setNewDisplayName(user?.display_name || '');
    };

    return (
        <>
            {/* Slim Profile Trigger with Floating Dropdown */}
            <DropdownMenu>
                <DropdownMenuTrigger asChild>
                    <Button
                        variant="ghost"
                        className="w-full h-auto p-3 rounded-lg justify-start gap-3 hover:bg-sidebar-accent data-[state=open]:bg-sidebar-accent"
                    >
                        <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold text-lg shadow-lg shrink-0">
                            {displayName.charAt(0).toUpperCase()}
                        </div>
                        <div className="flex-1 text-left min-w-0">
                            <div className="text-sm font-medium text-sidebar-foreground truncate">
                                {displayName}
                            </div>
                            <Badge variant="outline" className="text-xs capitalize border-sidebar-border text-sidebar-foreground/70">
                                {user?.role || 'User'}
                            </Badge>
                        </div>
                        <MoreHorizontal className="w-4 h-4 text-sidebar-foreground/50 shrink-0" />
                    </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                    className="w-56 rounded-lg"
                    side="top"
                    align="start"
                    sideOffset={4}
                >
                    <DropdownMenuLabel className="p-0 font-normal">
                        <div className="flex items-center gap-2 px-2 py-1.5 text-left text-sm">
                            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold">
                                {displayName.charAt(0).toUpperCase()}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="truncate font-semibold">{displayName}</div>
                                <div className="truncate text-xs text-muted-foreground capitalize">{user?.role}</div>
                            </div>
                        </div>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                        onClick={() => {
                            resetNameForm();
                            setIsNameDialogOpen(true);
                        }}
                        className="cursor-pointer"
                    >
                        <UserPen className="mr-2 h-4 w-4" />
                        Edit Display Name
                    </DropdownMenuItem>
                    <DropdownMenuItem
                        onClick={() => {
                            resetPasswordForm();
                            setIsPasswordDialogOpen(true);
                        }}
                        className="cursor-pointer"
                    >
                        <KeyRound className="mr-2 h-4 w-4" />
                        Change Password
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                        onClick={onLogout}
                        className="cursor-pointer text-destructive focus:text-destructive"
                    >
                        <LogOut className="mr-2 h-4 w-4" />
                        Logout
                    </DropdownMenuItem>
                </DropdownMenuContent>
            </DropdownMenu>

            {/* Edit Display Name Dialog */}
            <Dialog open={isNameDialogOpen} onOpenChange={setIsNameDialogOpen}>
                <DialogContent className="bg-card border-border">
                    <DialogHeader>
                        <DialogTitle className="text-card-foreground">✏️ Change Display Name</DialogTitle>
                        <DialogDescription className="text-muted-foreground">
                            This name will be displayed in the application
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="display_name" className="text-foreground">
                                New Display Name
                            </Label>
                            <Input
                                id="display_name"
                                placeholder="Enter new name..."
                                value={newDisplayName}
                                onChange={(e) => setNewDisplayName(e.target.value)}
                                className="bg-background border-input text-foreground"
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setIsNameDialogOpen(false)}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={handleUpdateDisplayName}
                            disabled={isUpdatingName}
                        >
                            {isUpdatingName ? (
                                <>
                                    <Spinner />
                                    Saving...
                                </>
                            ) : (
                                'Save'
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Change Password Dialog */}
            <Dialog open={isPasswordDialogOpen} onOpenChange={(open) => {
                setIsPasswordDialogOpen(open);
                if (!open) resetPasswordForm();
            }}>
                <DialogContent className="bg-card border-border">
                    <DialogHeader>
                        <DialogTitle className="text-card-foreground">🔒 Change Password</DialogTitle>
                        <DialogDescription className="text-muted-foreground">
                            Enter your current password and new password
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="current_password" className="text-foreground">
                                Current Password
                            </Label>
                            <Input
                                id="current_password"
                                type="password"
                                placeholder="Current password..."
                                value={currentPassword}
                                onChange={(e) => setCurrentPassword(e.target.value)}
                                className="bg-background border-input text-foreground"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="new_password" className="text-foreground">
                                New Password
                            </Label>
                            <Input
                                id="new_password"
                                type="password"
                                placeholder="New password..."
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
                                className="bg-background border-input text-foreground"
                            />
                            <p className="text-xs text-muted-foreground">Minimum 6 characters</p>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="confirm_password" className="text-foreground">
                                Confirm New Password
                            </Label>
                            <Input
                                id="confirm_password"
                                type="password"
                                placeholder="Repeat new password..."
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                className="bg-background border-input text-foreground"
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setIsPasswordDialogOpen(false)}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={handleChangePassword}
                            disabled={isLoading}
                        >
                            {isLoading ? (
                                <>
                                    <Spinner />
                                    Saving...
                                </>
                            ) : (
                                'Change Password'
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
