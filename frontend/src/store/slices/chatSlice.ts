/**
 * Chat Redux Slice
 * Handles chat messages and Q&A state
 */
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { apiClient } from '@/lib/api';

interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    table_name?: string;
    code?: string;
    explanation?: string;
    ui_components?: any[];
    has_error?: boolean;
    timestamp: number;
}

export interface ChatSession {
    id: string;
    title: string;
    updated_at: string;
}

interface ChatState {
    sessions: ChatSession[];
    currentSessionId: string | null;
    messages: ChatMessage[];
    isLoading: boolean;
    error: string | null;
    pendingQuestion: string | null;
    showTableSelector: boolean;
    streamingStatus: string | null;
}

const initialState: ChatState = {
    sessions: [],
    currentSessionId: null,
    messages: [],
    isLoading: false,
    error: null,
    pendingQuestion: null,
    showTableSelector: false,
    streamingStatus: null,
};


// Async Thunks
// Async Thunks

export const fetchSessions = createAsyncThunk(
    'chat/fetchSessions',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState() as { auth: { token: string } };
            const response = await apiClient.get('/api/chats', {
                headers: { Authorization: `Bearer ${state.auth.token}` }
            });
            return response.data;
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.detail || 'Failed to fetch sessions');
        }
    }
);

export const createSession = createAsyncThunk(
    'chat/createSession',
    async (title: string = "New Chat", { getState, rejectWithValue }) => {
        try {
            const state = getState() as { auth: { token: string } };
            const response = await apiClient.post('/api/chats', { title }, {
                headers: { Authorization: `Bearer ${state.auth.token}` }
            });
            return response.data;
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.detail || 'Failed to create session');
        }
    }
);

export const deleteSession = createAsyncThunk(
    'chat/deleteSession',
    async (chatId: string, { getState, rejectWithValue }) => {
        try {
            const state = getState() as { auth: { token: string } };
            await apiClient.delete(`/api/chats/${chatId}`, {
                headers: { Authorization: `Bearer ${state.auth.token}` }
            });
            return chatId;
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.detail || 'Failed to delete session');
        }
    }
);

export const renameSession = createAsyncThunk(
    'chat/renameSession',
    async ({ chatId, title }: { chatId: string, title: string }, { getState, rejectWithValue }) => {
        try {
            const state = getState() as { auth: { token: string } };
            const response = await apiClient.put(`/api/chats/${chatId}`, { title }, {
                headers: { Authorization: `Bearer ${state.auth.token}` }
            });
            return response.data;
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.detail || 'Failed to rename session');
        }
    }
);

export const loadChatHistory = createAsyncThunk(
    'chat/loadChatHistory',
    async (chatId: string, { getState, rejectWithValue }) => {
        try {
            const state = getState() as { auth: { token: string } };
            const response = await apiClient.get(`/api/chats/${chatId}`, {
                headers: { Authorization: `Bearer ${state.auth.token}` }
            });
            return response.data; // { chat, messages }
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.detail || 'Failed to load history');
        }
    }
);

export const askQuestion = createAsyncThunk(
    'chat/askQuestion',
    async (
        { question, tableId }: { question: string; tableId: string },
        { getState, dispatch, rejectWithValue }
    ) => {
        try {
            const state = getState() as { auth: { token: string }, chat: ChatState };
            let sessionId = state.chat.currentSessionId;

            // Auto-create session if none exists
            if (!sessionId) {
                const newSession = await dispatch(createSession(question.slice(0, 30))).unwrap();
                sessionId = newSession.id;
            }

            const response = await apiClient.post(
                '/api/chat/ask',
                { question, table_id: tableId, chat_id: sessionId },
                { headers: { Authorization: `Bearer ${state.auth.token}` } }
            );

            return response.data;
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.detail || 'Failed to process question');
        }
    }
);

// Streaming question using SSE
export const streamQuestion = createAsyncThunk(
    'chat/streamQuestion',
    async (
        { question, tableId = '' }: { question: string; tableId?: string },
        { getState, dispatch, rejectWithValue }
    ) => {
        try {
            const state = getState() as { auth: { token: string }, chat: ChatState };
            const token = state.auth.token;
            const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:1234';

            let sessionId = state.chat.currentSessionId;
            // Auto-create session if none exists
            if (!sessionId) {
                const newSession = await dispatch(createSession(question.slice(0, 30))).unwrap();
                sessionId = newSession.id;
            }

            const response = await fetch(`${API_BASE}/api/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({ question, table_id: tableId, chat_id: sessionId }),
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const reader = response.body?.getReader();
            if (!reader) throw new Error('No response body');

            const decoder = new TextDecoder();
            let finalResult: any = null;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.type === 'progress') {
                                dispatch(setStreamingStatus(data.message));
                            } else if (data.type === 'result') {
                                finalResult = data;
                            } else if (data.type === 'error') {
                                throw new Error(data.message);
                            }
                        } catch (e) {
                            // Ignore parse errors for incomplete chunks
                        }
                    }
                }
            }

            if (!finalResult) {
                throw new Error('No result received');
            }

            return finalResult;
        } catch (error: any) {
            return rejectWithValue(error.message || 'Streaming failed');
        }
    }
);

const chatSlice = createSlice({
    name: 'chat',
    initialState,
    reducers: {
        addMessage: (state, action: PayloadAction<Omit<ChatMessage, 'id' | 'timestamp'>>) => {
            state.messages.push({
                ...action.payload,
                id: Math.random().toString(36).substring(7),
                timestamp: Date.now(),
            });
        },
        clearMessages: (state) => {
            state.messages = [];
        },
        setPendingQuestion: (state, action: PayloadAction<string | null>) => {
            state.pendingQuestion = action.payload;
        },
        setShowTableSelector: (state, action: PayloadAction<boolean>) => {
            state.showTableSelector = action.payload;
        },
        clearError: (state) => {
            state.error = null;
        },
        setCurrentSession: (state, action: PayloadAction<string | null>) => {
            state.currentSessionId = action.payload;
            if (action.payload === null) {
                state.messages = []; // Clear view if deselected
            }
        },
        setStreamingStatus: (state, action: PayloadAction<string | null>) => {
            state.streamingStatus = action.payload;
        },
    },
    extraReducers: (builder) => {
        builder
            // Sessions
            .addCase(fetchSessions.fulfilled, (state, action) => {
                state.sessions = action.payload;
            })
            .addCase(createSession.fulfilled, (state, action) => {
                state.sessions.unshift(action.payload);
                state.currentSessionId = action.payload.id;
                state.messages = []; // New session empty
            })
            // Delete Session
            .addCase(deleteSession.fulfilled, (state, action) => {
                state.sessions = state.sessions.filter(s => s.id !== action.payload);
                if (state.currentSessionId === action.payload) {
                    state.currentSessionId = null;
                    state.messages = [];
                }
            })
            // Rename Session
            .addCase(renameSession.fulfilled, (state, action) => {
                const index = state.sessions.findIndex(s => s.id === action.payload.id);
                if (index !== -1) {
                    state.sessions[index] = action.payload;
                }
            })
            .addCase(loadChatHistory.pending, (state) => {
                state.isLoading = true;
                state.messages = [];
            })
            .addCase(loadChatHistory.fulfilled, (state, action) => {
                state.isLoading = false;
                state.currentSessionId = action.payload.chat.id;
                state.messages = action.payload.messages.map((msg: any) => ({
                    id: msg.id,
                    role: msg.role,
                    content: msg.content,
                    timestamp: new Date(msg.created_at).getTime(),
                    ...msg.metadata // Expand metadata like table_id, code, etc.
                }));
            })
            .addCase(loadChatHistory.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload as string;
            })

            // Ask Question
            .addCase(askQuestion.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(askQuestion.fulfilled, (state, action) => {
                state.isLoading = false;
                state.messages.push({
                    id: Math.random().toString(36).substring(7),
                    role: 'assistant',
                    content: action.payload.response,
                    code: action.payload.code,
                    ui_components: action.payload.ui_components,
                    timestamp: Date.now(),
                });
            })
            .addCase(askQuestion.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload as string;
                state.messages.push({
                    id: Math.random().toString(36).substring(7),
                    role: 'assistant',
                    content: `❌ Error: ${action.payload}`,
                    timestamp: Date.now(),
                });
            })
            // streamQuestion handlers
            .addCase(streamQuestion.pending, (state) => {
                state.isLoading = true;
                state.error = null;
                state.streamingStatus = null;
            })

            .addCase(streamQuestion.fulfilled, (state, action) => {
                state.isLoading = false;
                state.streamingStatus = null;

                // Standard response handling
                state.messages.push({
                    id: Math.random().toString(36).substring(7),
                    role: 'assistant',
                    content: action.payload.response || '',
                    code: action.payload.code,
                    explanation: action.payload.explanation,
                    ui_components: action.payload.ui_components || [],
                    has_error: action.payload.has_error,
                    timestamp: Date.now(),
                });
            })
            .addCase(streamQuestion.rejected, (state, action) => {
                state.isLoading = false;
                state.streamingStatus = null;
                state.error = action.payload as string;
                state.messages.push({
                    id: Math.random().toString(36).substring(7),
                    role: 'assistant',
                    content: `❌ Error: ${action.payload}`,
                    timestamp: Date.now(),
                });
            });
    },
});

export const {
    addMessage,
    clearMessages,
    setPendingQuestion,
    setShowTableSelector,
    clearError,
    setStreamingStatus,
    setCurrentSession,
} = chatSlice.actions;
export default chatSlice.reducer;
