/**
 * Tables Redux Slice
 * Handles cached tables and data management
 */
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { apiClient } from '@/lib/api';

export interface TableInfo {
    cache_path: string;
    display_name: string;
    original_file: string;
    sheet_name: string | null;
    n_rows: number;
    n_cols: number;
    cached_at: string;
    file_size_mb: number;
    description: string | null;
}

interface RankedTable {
    cache_path: string;
    display_name: string;
    n_rows: number;
    score: number;
}

interface TablesState {
    tables: TableInfo[];
    rankedTables: RankedTable[];
    selectedTable: TableInfo | null;
    isLoading: boolean;
    error: string | null;
}

const initialState: TablesState = {
    tables: [],
    rankedTables: [],
    selectedTable: null,
    isLoading: false,
    error: null,
};

// Async Thunks
export const fetchTables = createAsyncThunk(
    'tables/fetchTables',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState() as { auth: { token: string } };

            const response = await apiClient.get('/api/tables', {
                headers: { Authorization: `Bearer ${state.auth.token}` },
            });

            return response.data;
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.detail || 'Failed to fetch tables');
        }
    }
);

export const rankTables = createAsyncThunk(
    'tables/rankTables',
    async (question: string, { getState, rejectWithValue }) => {
        try {
            const state = getState() as { auth: { token: string } };

            const response = await apiClient.post(
                '/api/tables/rank',
                { question },
                { headers: { Authorization: `Bearer ${state.auth.token}` } }
            );

            return response.data;
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.detail || 'Failed to rank tables');
        }
    }
);

export const deleteTable = createAsyncThunk(
    'tables/deleteTable',
    async (tableId: string, { getState, rejectWithValue }) => {
        try {
            const state = getState() as { auth: { token: string } };

            await apiClient.delete(`/api/tables/${encodeURIComponent(tableId)}`, {
                headers: { Authorization: `Bearer ${state.auth.token}` },
            });

            return tableId;
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.detail || 'Failed to delete table');
        }
    }
);

const tablesSlice = createSlice({
    name: 'tables',
    initialState,
    reducers: {
        setSelectedTable: (state, action: PayloadAction<TableInfo | null>) => {
            state.selectedTable = action.payload;
        },
        clearError: (state) => {
            state.error = null;
        },
    },
    extraReducers: (builder) => {
        builder
            // Fetch tables
            .addCase(fetchTables.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(fetchTables.fulfilled, (state, action) => {
                state.isLoading = false;
                state.tables = action.payload;
            })
            .addCase(fetchTables.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload as string;
            })
            // Rank tables
            .addCase(rankTables.pending, (state) => {
                state.isLoading = true;
            })
            .addCase(rankTables.fulfilled, (state, action) => {
                state.isLoading = false;
                state.rankedTables = action.payload;
            })
            .addCase(rankTables.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload as string;
            })
            // Delete table
            .addCase(deleteTable.pending, (state) => {
                state.isLoading = true;
            })
            .addCase(deleteTable.fulfilled, (state, action) => {
                state.isLoading = false;
                state.tables = state.tables.filter((t) => t.cache_path !== action.payload);
            })
            .addCase(deleteTable.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload as string;
            });
    },
});

export const { setSelectedTable, clearError } = tablesSlice.actions;
export default tablesSlice.reducer;
