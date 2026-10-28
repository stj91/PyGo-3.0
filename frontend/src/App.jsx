import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { UserProvider } from './context/UserContext';
import { AppRoutes } from './routes/AppRoutes';

export default function App() {
  return (
    <UserProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </UserProvider>
  );
}