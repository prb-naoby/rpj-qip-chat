import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface OneDriveFile {
    id: string;
    name: string;
    path: string;
    size: number;
    downloadUrl: string;
    webUrl: string;
    lastModified: string;
}

interface AnalysisResult {
    summary: string;
    issues_found: string[];
    transform_code: string;
    needs_transform: boolean;
    validation_notes: string[];
    explanation: string;
    preview_data: any[];
    has_error: boolean;
}

interface TransformPreview {
    columns: string[];
    preview_data: any[];
    error?: string;
}

interface OneDriveState {
    // File Browser
    files: OneDriveFile[];
    filesLoaded: boolean;

    // Selection
    selectedFile: OneDriveFile | null;
    sheets: string[];
    selectedSheet: string;

    // Preview & Analysis
    previewTableId: string | null;
    transformInput: string;
    analysisResult: AnalysisResult | null;
    transformedPreview: TransformPreview | null;

    saveMode: 'new' | 'append';
    targetTableId: string;
    appendDescription: string;

    // Async Job Tracking
    activeJobId: string | null;
}

const initialState: OneDriveState = {
    files: [],
    filesLoaded: false,
    selectedFile: null,
    sheets: [],
    selectedSheet: "",
    previewTableId: null,
    transformInput: '',
    analysisResult: null,
    transformedPreview: null,
    saveMode: 'new',
    targetTableId: '',
    appendDescription: '',
    activeJobId: null
};

export const oneDriveSlice = createSlice({
    name: 'oneDrive',
    initialState,
    reducers: {
        setFiles: (state, action: PayloadAction<OneDriveFile[]>) => {
            state.files = action.payload;
            state.filesLoaded = true;
        },
        setSelectedFile: (state, action: PayloadAction<OneDriveFile | null>) => {
            state.selectedFile = action.payload;
            // Reset dependent states
            if (action.payload?.id !== state.selectedFile?.id) {
                state.sheets = [];
                state.selectedSheet = "";
                state.previewTableId = null;
                state.transformInput = "";
                state.analysisResult = null;
                state.transformedPreview = null;
                state.targetTableId = "";
                state.activeJobId = null;
            }
        },
        setSheets: (state, action: PayloadAction<string[]>) => {
            state.sheets = action.payload;
        },
        setSelectedSheet: (state, action: PayloadAction<string>) => {
            state.selectedSheet = action.payload;
        },
        setPreviewTableId: (state, action: PayloadAction<string | null>) => {
            state.previewTableId = action.payload;
        },
        setTransformInput: (state, action: PayloadAction<string>) => {
            state.transformInput = action.payload;
        },
        setAnalysisResult: (state, action: PayloadAction<AnalysisResult | null>) => {
            state.analysisResult = action.payload;
        },
        setTransformedPreview: (state, action: PayloadAction<TransformPreview | null>) => {
            state.transformedPreview = action.payload;
        },
        setSaveMode: (state, action: PayloadAction<'new' | 'append'>) => {
            state.saveMode = action.payload;
        },
        setTargetTableId: (state, action: PayloadAction<string>) => {
            state.targetTableId = action.payload;
        },
        setAppendDescription: (state, action: PayloadAction<string>) => {
            state.appendDescription = action.payload;
        },
        setActiveJobId: (state, action: PayloadAction<string | null>) => {
            state.activeJobId = action.payload;
        },
        resetState: (state) => {
            return initialState;
        }
    }
});

export const {
    setFiles,
    setSelectedFile,
    setSheets,
    setSelectedSheet,
    setPreviewTableId,
    setTransformInput,
    setAnalysisResult,
    setTransformedPreview,
    setSaveMode,
    setTargetTableId,
    setAppendDescription,
    setActiveJobId,
    resetState
} = oneDriveSlice.actions;

export default oneDriveSlice.reducer;
