/**
 * Redux Store Configuration for QIP Data Assistant
 */
import { configureStore } from '@reduxjs/toolkit';
import authReducer from './slices/authSlice';
import chatReducer from './slices/chatSlice';
import tablesReducer from './slices/tablesSlice';
import oneDriveReducer from './slices/oneDriveSlice';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    chat: chatReducer,
    tables: tablesReducer,
    oneDrive: oneDriveReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: false,
    }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
