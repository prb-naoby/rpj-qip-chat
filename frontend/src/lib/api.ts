/**
 * API Client for QIP Data Assistant
 * Axios wrapper for backend communication via Next.js proxy
 * 
 * All requests go through /api/proxy which forwards to the backend server.
 * This keeps the backend URL hidden from the client and allows the frontend
 * to be accessed via the same domain as the API.
 */
import axios from 'axios';

// Use proxy route - this works both client-side (relative URL) and server-side
const API_BASE_URL = '/api/proxy';

export const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});


// Request interceptor to add auth token
apiClient.interceptors.request.use(
    (config) => {
        if (typeof window !== 'undefined') {
            const token = localStorage.getItem('token');
            if (token && !config.headers.Authorization) {
                config.headers.Authorization = `Bearer ${token}`;
            }
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            // Token expired or invalid
            if (typeof window !== 'undefined') {
                localStorage.removeItem('token');
                window.location.href = '/login';
            }
        }
        return Promise.reject(error);
    }
);

// API helper functions
export const api = {
    // Expose client for direct access
    apiClient,

    // Auth
    login: async (username: string, password: string) => {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        return apiClient.post('/auth/token', formData.toString(), {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        });
    },

    getMe: () => apiClient.get('/auth/me'),

    updateProfile: (displayName: string) =>
        apiClient.patch('/auth/profile', { display_name: displayName }),

    changePassword: (currentPassword: string, newPassword: string) =>
        apiClient.patch('/auth/password', {
            current_password: currentPassword,
            new_password: newPassword,
        }),

    // Tables
    getTables: () => apiClient.get('/api/tables'),

    getTablePreview: (tableId: string, rows = 20) =>
        apiClient.get(`/api/tables/${encodeURIComponent(tableId)}/preview?rows=${rows}`),

    deleteTable: (tableId: string) =>
        apiClient.delete(`/api/tables/${encodeURIComponent(tableId)}`),

    updateTableDescription: (tableId: string, description: string, displayName?: string) =>
        apiClient.patch(`/api/tables/${encodeURIComponent(tableId)}`, { description, display_name: displayName }),

    rankTables: (question: string) =>
        apiClient.post('/api/tables/rank', { question }),

    downloadTableCsv: async (tableId: string, filename: string) => {
        const response = await apiClient.get(`/api/tables/${encodeURIComponent(tableId)}/download`, {
            responseType: 'blob'
        });
        // Trigger browser download
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
    },

    // Chat
    askQuestion: (question: string, tableId: string) =>
        apiClient.post('/api/chat/ask', { question, table_id: tableId }),

    // OneDrive
    getOneDriveStatus: () => apiClient.get('/api/onedrive/status'),

    listOneDriveSubfolders: () => apiClient.get('/api/onedrive/subfolders'),

    listOneDriveFiles: (subfolder?: string) =>
        apiClient.get('/api/onedrive/files', { params: subfolder ? { subfolder } : {} }),

    getOneDriveSheets: (fileId: string, downloadUrl: string) =>
        apiClient.post('/api/onedrive/sheets', { fileId, downloadUrl }),

    loadOneDriveSheet: (fileId: string, downloadUrl: string, filename: string, displayName: string, sheetName?: string) =>
        apiClient.post('/api/onedrive/load-sheet', {
            file_id: fileId,
            download_url: downloadUrl,
            filename,
            display_name: displayName,
            sheet_name: sheetName
        }),

    uploadToOneDrive: (tableId: string, subfolder: string, filename?: string) =>
        apiClient.post('/api/onedrive/upload', {
            table_id: tableId,
            subfolder,
            filename
        }),

    // Ingestion
    ingestAllDocuments: (dryRun: boolean = false) =>
        apiClient.post('/api/documents/ingest', { dry_run: dryRun }),

    // Files
    uploadFile: (file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        return apiClient.post('/api/files/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
    },

    // AI Data Analysis
    analyzeFile: (tableId: string, userDescription?: string, metadata?: {
        selectedFile?: { id: string; name: string; path: string };
        selectedSheet?: string;
        displayName?: string;
    }) =>
        apiClient.post('/api/files/analyze', {
            table_id: tableId,
            user_description: userDescription,
            metadata: metadata
        }),

    previewTransform: (tableId: string, transformCode: string) =>
        apiClient.post('/api/files/transform/preview', {
            table_id: tableId,
            transform_code: transformCode
        }),

    confirmTransform: (tableId: string, transformCode: string, displayName?: string, replaceOriginal: boolean = false) =>
        apiClient.post('/api/files/transform/confirm', {
            table_id: tableId,
            transform_code: transformCode,
            display_name: displayName,
            replace_original: replaceOriginal
        }),

    refineTransform: (tableId: string, transformCode: string, feedback: string) =>
        apiClient.post('/api/files/transform/refine', {
            table_id: tableId,
            transform_code: transformCode,
            feedback: feedback
        }),

    appendToTable: (targetTableId: string, sourceTableId: string, description: string) =>
        apiClient.post('/api/files/append', {
            target_table_id: targetTableId,
            source_table_id: sourceTableId,
            description: description
        }),

    // Smart Append with Transform
    validateAppend: (sourceTableId: string, targetTableId: string) =>
        apiClient.post('/api/files/append/validate', {
            source_table_id: sourceTableId,
            target_table_id: targetTableId
        }),

    previewAppendTransform: (sourceTableId: string, targetTableId: string, userFeedback?: string) =>
        apiClient.post('/api/files/append/preview-transform', {
            source_table_id: sourceTableId,
            target_table_id: targetTableId,
            user_feedback: userFeedback
        }),

    confirmAppendTransform: (sourceTableId: string, targetTableId: string, description: string, transformCode?: string) =>
        apiClient.post('/api/files/append/confirm-transform', {
            source_table_id: sourceTableId,
            target_table_id: targetTableId,
            description: description,
            transform_code: transformCode
        }),

    generateAppendTransform: (sourceTableId: string, targetTableId: string, userDescription: string) =>
        apiClient.post('/api/files/append/generate-transform', {
            source_table_id: sourceTableId,
            target_table_id: targetTableId,
            user_description: userDescription
        }),

    // Admin - User Management
    adminListUsers: () => apiClient.get('/api/admin/users'),

    adminCreateUser: (username: string, password: string, role: string = 'user', displayName?: string) =>
        apiClient.post('/api/admin/users', { username, password, role, display_name: displayName }),

    adminDeleteUser: (username: string) => apiClient.delete(`/api/admin/users/${username}`),

    // Admin - Pending Users
    adminListPendingUsers: () => apiClient.get('/api/admin/pending-users'),

    adminApproveUser: (userId: number) => apiClient.post(`/api/admin/pending-users/${userId}/approve`),

    adminRejectUser: (userId: number) => apiClient.post(`/api/admin/pending-users/${userId}/reject`),

    // Jobs
    getJobs: (type?: string) =>
        apiClient.get('/api/jobs', { params: { type } }),

    getJobStatus: (jobId: string) => apiClient.get(`/api/jobs/${jobId}`),

    deleteJob: (jobId: string) => apiClient.delete(`/api/jobs/${jobId}`),

    clearJobs: (period: 'hour' | 'today' | '3days' | 'all') =>
        apiClient.delete('/api/jobs/clear', { params: { period } }),

    // Signup (public)
    signup: (username: string, password: string, email?: string) =>
        apiClient.post('/auth/signup', { username, password, email }),
};

export default api;

