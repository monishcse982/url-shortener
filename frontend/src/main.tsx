import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './AuthContext'
import { DotGridBackground } from './components/Ui'
import { RequireAuth } from './RequireAuth'
import { Callback } from './pages/Callback'
import { Links } from './pages/Links'
import { ManageLink } from './pages/ManageLink'
import { SignIn } from './pages/SignIn'
import './styles.css'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><QueryClientProvider client={queryClient}><AuthProvider><BrowserRouter><DotGridBackground><Routes>
    <Route path="/" element={<SignIn />} />
    <Route path="/auth/callback" element={<Callback />} />
    <Route path="/links" element={<RequireAuth><Links /></RequireAuth>} />
    <Route path="/links/:id" element={<RequireAuth><ManageLink /></RequireAuth>} />
    <Route path="*" element={<Navigate to="/links" replace />} />
  </Routes></DotGridBackground></BrowserRouter></AuthProvider></QueryClientProvider></React.StrictMode>,
)
