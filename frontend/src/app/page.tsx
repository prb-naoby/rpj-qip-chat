'use client';

/**
 * Main App Page
 * Dashboard with ShadCN sidebar navigation for Chat, OneDrive, Upload, and Manage Tables
 */
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchCurrentUser, logout } from '@/store/slices/authSlice';
import { fetchTables } from '@/store/slices/tablesSlice';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { Spinner } from '@/components/ui/spinner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { AppSidebar, TabType } from '@/components/AppSidebar';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import ChatTab from '@/components/tabs/ChatTab';
import OneDriveTab from '@/components/tabs/OneDriveTab';
import UploadTab from '@/components/tabs/UploadTab';
import ManageTab from '@/components/tabs/ManageTab';

export default function HomePage() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const { isAuthenticated, isLoading } = useAppSelector((state) => state.auth);
  const [activeTab, setActiveTab] = useState<TabType>('chat');

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      dispatch(fetchCurrentUser());
    } else {
      router.push('/login');
    }
  }, [dispatch, router]);

  useEffect(() => {
    if (isAuthenticated) {
      dispatch(fetchTables());
    }
  }, [isAuthenticated, dispatch]);

  const handleLogout = () => {
    dispatch(logout());
    router.push('/login');
  };

  if (isLoading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="min-h-screen flex items-center justify-center bg-background"
      >
        <div className="flex items-center gap-3 text-muted-foreground">
          <Spinner className="size-6" />
          <span>Loading...</span>
        </div>
      </motion.div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'chat':
        return <ChatTab />;
      case 'onedrive':
        return <OneDriveTab />;
      case 'upload':
        return <UploadTab />;
      case 'manage':
        return <ManageTab />;
    }
  };

  return (
    <TooltipProvider>
      <SidebarProvider defaultOpen>
        <AppSidebar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onLogout={handleLogout}
        />
        <SidebarInset>
          <header className="flex h-14 items-center gap-4 border-b border-border px-4 bg-background">
            <SidebarTrigger className="-ml-1" />
            <h1 className="text-lg font-semibold text-foreground">
              {activeTab === 'chat' && '💬 Chat'}
              {activeTab === 'onedrive' && '☁️ OneDrive'}
              {activeTab === 'upload' && '⬆️ Upload'}
              {activeTab === 'manage' && '🛠️ Manage Tables'}
            </h1>
          </header>
          <main className="flex-1 p-2 md:p-4 lg:p-6 bg-background" role="main">
            <div className="w-full max-w-7xl mx-auto">
              <ErrorBoundary>
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeTab}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.2 }}
                  >
                    {renderTabContent()}
                  </motion.div>
                </AnimatePresence>
              </ErrorBoundary>
            </div>
          </main>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  );
}
