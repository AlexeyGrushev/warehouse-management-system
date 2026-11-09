import { Navigate, Route, Routes } from 'react-router-dom'

import { AppLayout } from './components/AppLayout'
import { LoginPage } from './features/auth/LoginPage'
import { ProtectedRoute } from './features/auth/ProtectedRoute'
import { MovementsPage } from './features/movements/MovementsPage'
import { ProductsPage } from './features/products/ProductsPage'
import { ReservationsPage } from './features/reservations/ReservationsPage'
import { StocktakingPage } from './features/stocktaking/StocktakingPage'
import { StocktakingsPage } from './features/stocktaking/StocktakingsPage'
import { StockPage } from './features/stock/StockPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/stock" element={<StockPage />} />
          <Route path="/movements" element={<MovementsPage />} />
          <Route path="/reservations" element={<ReservationsPage />} />
          <Route path="/stocktakings" element={<StocktakingsPage />} />
          <Route path="/stocktakings/:id" element={<StocktakingPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/products" replace />} />
    </Routes>
  )
}
