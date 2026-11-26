import {
  ApartmentOutlined,
  AuditOutlined,
  DatabaseOutlined,
  HistoryOutlined,
  LockOutlined,
  LogoutOutlined,
  ShoppingOutlined,
  TeamOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Badge, Button, Layout, Menu, Space, Tag, Typography } from 'antd'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

import { fetchLowStock } from '../api/alerts'
import { useAuth } from '../features/auth/auth-state'

const ROLE_LABELS = {
  admin: 'администратор',
  storekeeper: 'кладовщик',
  viewer: 'наблюдатель',
} as const

const MENU_ITEMS = [
  { key: '/products', icon: <ShoppingOutlined />, label: 'Товары' },
  { key: '/categories', icon: <ApartmentOutlined />, label: 'Категории' },
  { key: '/suppliers', icon: <TeamOutlined />, label: 'Поставщики' },
  { key: '/stock', icon: <DatabaseOutlined />, label: 'Остатки' },
  { key: '/low-stock', icon: <WarningOutlined />, label: 'Заканчивается' },
  { key: '/reservations', icon: <LockOutlined />, label: 'Резервы' },
  { key: '/stocktakings', icon: <AuditOutlined />, label: 'Инвентаризация' },
  { key: '/movements', icon: <HistoryOutlined />, label: 'Журнал движений' },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  // Число товаров ниже минимума: тот же отчёт, что на странице «Заканчивается», берём только total.
  // Каркас живёт между переходами, поэтому лишних запросов нет; после операций ключ 'alerts' сбрасывается.
  const lowStockCount = useQuery({
    queryKey: ['alerts', 'low-stock-count'],
    queryFn: () => fetchLowStock({ page: 1, size: 1 }),
    select: (result) => result.total,
    staleTime: 60_000,
  })
  const menuItems = MENU_ITEMS.map((item) =>
    item.key === '/low-stock'
      ? {
          ...item,
          label: (
            <Space size={6}>
              {item.label}
              <Badge size="small" count={lowStockCount.data ?? 0} overflowCount={99} />
            </Space>
          ),
        }
      : item,
  )

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Sider breakpoint="lg" collapsedWidth={0} width={230} theme="light">
        <Typography.Title level={4} style={{ padding: '16px 24px', margin: 0 }}>
          WMS
        </Typography.Title>
        <Menu
          mode="inline"
          selectedKeys={[`/${location.pathname.split('/')[1]}`]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Layout.Sider>
      <Layout>
        <Layout.Header
          style={{
            background: 'transparent',
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center',
          }}
        >
          <Space>
            <span>{user?.email}</span>
            {user && <Tag>{ROLE_LABELS[user.role]}</Tag>}
            <Button icon={<LogoutOutlined />} onClick={logout}>
              Выйти
            </Button>
          </Space>
        </Layout.Header>
        <Layout.Content style={{ margin: 24 }}>
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  )
}
