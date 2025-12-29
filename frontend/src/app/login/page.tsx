'use client';

/**
 * Login Page Component
 * Handles user authentication with username/password
 */
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { login, clearError } from '@/store/slices/authSlice';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { Spinner } from '@/components/ui/spinner';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { TooltipProvider } from '@/components/ui/tooltip';

export default function LoginPage() {
    const router = useRouter();
    const dispatch = useAppDispatch();
    const { isLoading, error, isAuthenticated } = useAppSelector((state) => state.auth);

    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');

    useEffect(() => {
        if (isAuthenticated) {
            router.push('/');
        }
    }, [isAuthenticated, router]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        dispatch(clearError());
        dispatch(login({ username, password }));
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-muted to-background relative">
            {/* Theme Toggle */}
            <div className="absolute top-4 right-4">
                <ThemeToggle />
            </div>

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: 'easeOut' }}
            >
                <Card className="w-full max-w-md mx-4 shadow-2xl border-border bg-card/80 backdrop-blur-sm">
                    <CardHeader className="text-center space-y-2">
                        <motion.div
                            className="text-4xl mb-2"
                            initial={{ scale: 0.8 }}
                            animate={{ scale: 1 }}
                            transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
                        >
                            🛍️
                        </motion.div>
                        <CardTitle className="text-2xl font-bold text-card-foreground">QIP Data Assistant</CardTitle>
                        <CardDescription className="text-muted-foreground">
                            Silakan login untuk melanjutkan
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleSubmit} className="space-y-4" aria-label="Login form">
                            <div className="space-y-2">
                                <Label htmlFor="username" className="text-foreground">Username</Label>
                                <Input
                                    id="username"
                                    type="text"
                                    placeholder="Masukkan username..."
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    className="bg-background border-input text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring"
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="password" className="text-foreground">Password</Label>
                                <Input
                                    id="password"
                                    type="password"
                                    placeholder="Masukkan password..."
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="bg-background border-input text-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring"
                                    required
                                />
                            </div>

                            {error && (
                                <motion.div
                                    className="p-3 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md"
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                >
                                    😕 {error}
                                </motion.div>
                            )}

                            <TooltipProvider>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <span tabIndex={0}>
                                            <Button
                                                type="submit"
                                                className="w-full cursor-pointer"
                                                disabled={isLoading || !username || !password}
                                            >
                                                {isLoading ? <><Spinner />Logging in...</> : 'Login'}
                                            </Button>
                                        </span>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p>
                                            {!username && !password
                                                ? 'Enter username and password'
                                                : !username
                                                    ? 'Enter username'
                                                    : !password
                                                        ? 'Enter password'
                                                        : isLoading
                                                            ? 'Authenticating...'
                                                            : 'Sign in to your account'}
                                        </p>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>
                        </form>

                        <div className="mt-4 text-center text-sm text-muted-foreground">
                            Belum punya akun?{' '}
                            <a href="/signup" className="text-primary hover:underline">
                                Daftar di sini
                            </a>
                        </div>
                    </CardContent>
                </Card>
            </motion.div>
        </div>
    );
}
