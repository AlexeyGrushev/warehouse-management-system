import { Spin } from 'antd'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from './auth-state'

export function ProtectedRoute() {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <Spin fullscreen />
  }
  if (user === null) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}
