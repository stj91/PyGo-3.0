import React from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useUser } from '../context/UserContext';
import { IconAlertCircle } from '@tabler/icons-react';

export const Layout = ({ children }) => {
  const { networkError } = useUser();

  return (
    <div className="min-h-screen bg-slate-50 bg-dot-pattern flex relative">
      {/* Banner de Error Global Fijo */}
      {networkError && (
        <div className="fixed top-0 inset-x-0 bg-rose-600 text-white text-center py-2 px-4 text-xs font-semibold z-50 shadow-md flex items-center justify-center gap-2">
          <IconAlertCircle className="w-4 h-4" />
          <span>Error de conexión con el servidor backend. Por favor verifica tu red o intenta más tarde.</span>
        </div>
      )}

      <Sidebar />
      <div className={`flex-1 ml-64 flex flex-col min-w-0 ${networkError ? 'mt-8' : ''}`}>
        <Header />
        <main className="p-8 flex-1">{children}</main>
      </div>
    </div>
  );
};