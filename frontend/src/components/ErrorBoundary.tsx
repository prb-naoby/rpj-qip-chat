'use client';

import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}

interface ErrorBoundaryProps {
    children: React.ReactNode;
    fallback?: React.ReactNode;
}

/**
 * Error Boundary Component
 * Catches JavaScript errors in child component tree and displays fallback UI.
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error('ErrorBoundary caught:', error, errorInfo);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <Card className="bg-destructive/10 border-destructive m-4">
                    <CardContent className="py-8 text-center">
                        <div className="text-4xl mb-4">⚠️</div>
                        <h2 className="text-lg font-semibold text-destructive mb-2">
                            Terjadi Kesalahan
                        </h2>
                        <p className="text-sm text-muted-foreground mb-4">
                            {this.state.error?.message || 'An unexpected error occurred'}
                        </p>
                        <Button
                            variant="outline"
                            onClick={this.handleReset}
                        >
                            Coba Lagi
                        </Button>
                    </CardContent>
                </Card>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
