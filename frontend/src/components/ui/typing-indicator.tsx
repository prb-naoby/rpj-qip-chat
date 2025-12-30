'use client';

/**
 * Typing Indicator Component
 * Shows animated dots to indicate AI is processing
 */
import { motion } from 'framer-motion';

interface TypingIndicatorProps {
    message?: string;
}

export function TypingIndicator({ message = 'Processing...' }: TypingIndicatorProps) {
    return (
        <div className="flex items-center gap-2 text-muted-foreground">
            <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                    <motion.span
                        key={i}
                        className="w-2 h-2 bg-primary/60 rounded-full"
                        animate={{
                            y: [0, -4, 0],
                            opacity: [0.4, 1, 0.4],
                        }}
                        transition={{
                            duration: 0.6,
                            repeat: Infinity,
                            delay: i * 0.15,
                        }}
                    />
                ))}
            </div>
            <span className="text-sm">{message}</span>
        </div>
    );
}

export default TypingIndicator;
