'use client';

/**
 * Signup Page Component
 * Handles user registration with admin approval workflow
 */
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { Spinner } from '@/components/ui/spinner';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { CheckCircle } from 'lucide-react';
import { api } from '@/lib/api';

export default function SignupPage() {
    const router = useRouter();

    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [email, setEmail] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        if (password !== confirmPassword) {
            setError('Passwords do not match');
            return;
        }

        if (password.length < 6) {
            setError('Password must be at least 6 characters');
            return;
        }

        setIsLoading(true);
        try {
            await api.signup(username, password, email || undefined);
            setSuccess(true);
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || 'Signup failed');
        } finally {
            setIsLoading(false);
        }
    };

    if (success) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-muted to-background relative">
                <div className="absolute top-4 right-4">
                    <ThemeToggle />
                </div>

                <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.4 }}
                >
                    <Card className="w-full max-w-md mx-4 shadow-2xl border-border bg-card/80 backdrop-blur-sm">
                        <CardContent className="pt-6">
                            <Alert className="border-green-500/50 bg-green-500/10">
                                <CheckCircle className="h-5 w-5 text-green-500" />
                                <AlertTitle className="text-green-600">Registration Successful!</AlertTitle>
                                <AlertDescription className="text-muted-foreground">
                                    Your account is pending admin approval.
                                    You will be able to login once an admin approves your registration.
                                </AlertDescription>
                            </Alert>
                            <div className="mt-6 text-center">
                                <Button onClick={() => router.push('/login')} className="w-full">
                                    Back to Login
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </motion.div>
            </div>
        );
    }

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
                            📝
                        </motion.div>
                        <CardTitle className="text-2xl font-bold text-card-foreground">Create New Account</CardTitle>
                        <CardDescription className="text-muted-foreground">
                            Fill in the form below to register
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="username" className="text-foreground">Username *</Label>
                                <Input
                                    id="username"
                                    type="text"
                                    placeholder="Enter username..."
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    className="bg-background border-input text-foreground"
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="email" className="text-foreground">Email (optional)</Label>
                                <Input
                                    id="email"
                                    type="email"
                                    placeholder="Enter email..."
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="bg-background border-input text-foreground"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="password" className="text-foreground">Password *</Label>
                                <Input
                                    id="password"
                                    type="password"
                                    placeholder="At least 6 characters..."
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="bg-background border-input text-foreground"
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="confirmPassword" className="text-foreground">Confirm Password *</Label>
                                <Input
                                    id="confirmPassword"
                                    type="password"
                                    placeholder="Repeat password..."
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    className="bg-background border-input text-foreground"
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

                            <Button
                                type="submit"
                                className="w-full"
                                disabled={isLoading || !username || !password || !confirmPassword}
                            >
                                {isLoading ? <><Spinner />Signing up...</> : 'Sign Up'}
                            </Button>
                        </form>

                        <div className="mt-4 text-center text-sm text-muted-foreground">
                            Already have an account?{' '}
                            <a href="/login" className="text-primary hover:underline">
                                Login here
                            </a>
                        </div>
                    </CardContent>
                </Card>
            </motion.div>
        </div>
    );
}
