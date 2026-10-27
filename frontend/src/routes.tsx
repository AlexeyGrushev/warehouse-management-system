import { Navigate, Route, Routes } from 'react-router-dom'

import { AppLayout } from './components/AppLayout'
import { LoginPage } from './features/auth/LoginPage'
import { ProtectedRoute } from './features/auth/ProtectedRoute'
import { ProductsPage } from './features/products/ProductsPage'
import { StockPage } from './features/stock/StockPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/stock" element={<StockPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/products" replace />} />
    </Routes>
  )
}
