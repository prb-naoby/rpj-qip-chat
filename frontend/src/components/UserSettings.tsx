'use client';

/**
 * User Settings Component
 * Allows users to change password and update display name
 * Following exim-chat pattern with sheet/dialog approach
 */
import { useState } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { changePassword, fetchCurrentUser } from '@/store/slices/authSlice';
import { api } from '@/lib/api';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
    SheetTrigger,
    SheetFooter,
} from '@/components/ui/sheet';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
    DialogFooter,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface UserSettingsProps {
    trigger?: React.ReactNode;
}

export default function UserSettings({ trigger }: UserSettingsProps) {
    const dispatch = useAppDispatch();
    const { user, isLoading } = useAppSelector((state) => state.auth);

    // State for sheet visibility
    const [isSheetOpen, setIsSheetOpen] = useState(false);

    // State for change display name
    const [newDisplayName, setNewDisplayName] = useState('');
    const [isUpdatingName, setIsUpdatingName] = useState(false);
    const [isNameDialogOpen, setIsNameDialogOpen] = useState(false);

    // State for change password
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [isPasswordDialogOpen, setIsPasswordDialogOpen] = useState(false);

    // Handle display name update
    const handleUpdateDisplayName = async () => {
        if (!newDisplayName.trim()) {
            toast.error('Nama tampilan tidak boleh kosong');
            return;
        }

        setIsUpdatingName(true);
        try {
            await api.updateProfile(newDisplayName.trim());
            toast.success('✅ Nama tampilan berhasil diperbarui');
            dispatch(fetchCurrentUser());
            setIsNameDialogOpen(false);
            setNewDisplayName('');
        } catch (error: any) {
            toast.error(`Gagal memperbarui: ${error.response?.data?.detail || error.message}`);
        } finally {
            setIsUpdatingName(false);
        }
    };

    // Handle password change
    const handleChangePassword = async () => {
        if (!currentPassword || !newPassword) {
            toast.error('Semua field harus diisi');
            return;
        }

        if (newPassword !== confirmPassword) {
            toast.error('Password baru tidak cocok');
            return;
        }

        if (newPassword.length < 6) {
            toast.error('Password minimal 6 karakter');
            return;
        }

        try {
            await dispatch(changePassword({
                current_password: currentPassword,
                new_password: newPassword,
            })).unwrap();

            toast.success('✅ Password berhasil diubah');
            setIsPasswordDialogOpen(false);
            setCurrentPassword('');
            setNewPassword('');
            setConfirmPassword('');
        } catch (error: any) {
            toast.error(`Gagal mengubah password: ${error}`);
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
        <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
            <SheetTrigger asChild>
                {trigger || (
                    <Button variant="ghost" size="sm" className="w-full justify-start">
                        ⚙️ Pengaturan
                    </Button>
                )}
            </SheetTrigger>
            <SheetContent className="bg-slate-800 border-slate-700 text-white">
                <SheetHeader>
                    <SheetTitle className="text-white">⚙️ Pengaturan Akun</SheetTitle>
                    <SheetDescription className="text-slate-400">
                        Kelola profil dan keamanan akun Anda
                    </SheetDescription>
                </SheetHeader>

                <div className="py-6 space-y-6">
                    {/* User Info Section */}
                    <div className="space-y-2">
                        <h3 className="text-sm font-medium text-slate-300">Informasi Akun</h3>
                        <div className="p-4 bg-slate-700/50 rounded-lg space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-slate-400">Username</span>
                                <span className="font-medium">{user?.username}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-slate-400">Nama Tampilan</span>
                                <span className="font-medium">{user?.display_name || user?.username}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-slate-400">Role</span>
                                <Badge variant="secondary" className="capitalize">
                                    {user?.role}
                                </Badge>
                            </div>
                        </div>
                    </div>

                    <Separator className="bg-slate-700" />

                    {/* Edit Display Name */}
                    <div className="space-y-3">
                        <h3 className="text-sm font-medium text-slate-300">Ubah Nama Tampilan</h3>
                        <Dialog open={isNameDialogOpen} onOpenChange={(open) => {
                            setIsNameDialogOpen(open);
                            if (open) resetNameForm();
                        }}>
                            <DialogTrigger asChild>
                                <Button variant="outline" className="w-full border-slate-600 text-slate-300 hover:bg-slate-700">
                                    ✏️ Edit Nama Tampilan
                                </Button>
                            </DialogTrigger>
                            <DialogContent className="bg-slate-800 border-slate-700">
                                <DialogHeader>
                                    <DialogTitle className="text-white">✏️ Ubah Nama Tampilan</DialogTitle>
                                    <DialogDescription className="text-slate-400">
                                        Nama ini akan ditampilkan di aplikasi
                                    </DialogDescription>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <Label htmlFor="display_name" className="text-slate-200">
                                            Nama Tampilan Baru
                                        </Label>
                                        <Input
                                            id="display_name"
                                            placeholder="Masukkan nama baru..."
                                            value={newDisplayName}
                                            onChange={(e) => setNewDisplayName(e.target.value)}
                                            className="bg-slate-700/50 border-slate-600 text-white"
                                        />
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button
                                        variant="outline"
                                        onClick={() => setIsNameDialogOpen(false)}
                                        className="border-slate-600"
                                    >
                                        Batal
                                    </Button>
                                    <Button
                                        onClick={handleUpdateDisplayName}
                                        disabled={isUpdatingName}
                                        className="bg-blue-600 hover:bg-blue-700"
                                    >
                                        {isUpdatingName ? (
                                            <>
                                                <Spinner />
                                                Menyimpan...
                                            </>
                                        ) : (
                                            'Simpan'
                                        )}
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    </div>

                    <Separator className="bg-slate-700" />

                    {/* Change Password */}
                    <div className="space-y-3">
                        <h3 className="text-sm font-medium text-slate-300">Keamanan</h3>
                        <Dialog open={isPasswordDialogOpen} onOpenChange={(open) => {
                            setIsPasswordDialogOpen(open);
                            if (!open) resetPasswordForm();
                        }}>
                            <DialogTrigger asChild>
                                <Button variant="outline" className="w-full border-slate-600 text-slate-300 hover:bg-slate-700">
                                    🔒 Ubah Password
                                </Button>
                            </DialogTrigger>
                            <DialogContent className="bg-slate-800 border-slate-700">
                                <DialogHeader>
                                    <DialogTitle className="text-white">🔒 Ubah Password</DialogTitle>
                                    <DialogDescription className="text-slate-400">
                                        Masukkan password lama dan password baru Anda
                                    </DialogDescription>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <Label htmlFor="current_password" className="text-slate-200">
                                            Password Saat Ini
                                        </Label>
                                        <Input
                                            id="current_password"
                                            type="password"
                                            placeholder="Password lama..."
                                            value={currentPassword}
                                            onChange={(e) => setCurrentPassword(e.target.value)}
                                            className="bg-slate-700/50 border-slate-600 text-white"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="new_password" className="text-slate-200">
                                            Password Baru
                                        </Label>
                                        <Input
                                            id="new_password"
                                            type="password"
                                            placeholder="Password baru (min 6 karakter)..."
                                            value={newPassword}
                                            onChange={(e) => setNewPassword(e.target.value)}
                                            className="bg-slate-700/50 border-slate-600 text-white"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="confirm_password" className="text-slate-200">
                                            Konfirmasi Password Baru
                                        </Label>
                                        <Input
                                            id="confirm_password"
                                            type="password"
                                            placeholder="Ulangi password baru..."
                                            value={confirmPassword}
                                            onChange={(e) => setConfirmPassword(e.target.value)}
                                            className="bg-slate-700/50 border-slate-600 text-white"
                                        />
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button
                                        variant="outline"
                                        onClick={() => setIsPasswordDialogOpen(false)}
                                        className="border-slate-600"
                                    >
                                        Batal
                                    </Button>
                                    <Button
                                        onClick={handleChangePassword}
                                        disabled={isLoading}
                                        className="bg-blue-600 hover:bg-blue-700"
                                    >
                                        {isLoading ? (
                                            <>
                                                <Spinner />
                                                Menyimpan...
                                            </>
                                        ) : (
                                            'Ubah Password'
                                        )}
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>
                    </div>
                </div>
            </SheetContent>
        </Sheet>
    );
}
