import { DatabaseOutlined, HistoryOutlined, LogoutOutlined, ShoppingOutlined } from '@ant-design/icons'
import { Button, Layout, Menu, Space, Tag, Typography } from 'antd'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../features/auth/auth-state'

const ROLE_LABELS = {
  admin: 'администратор',
  storekeeper: 'кладовщик',
  viewer: 'наблюдатель',
} as const

const MENU_ITEMS = [
  { key: '/products', icon: <ShoppingOutlined />, label: 'Товары' },
  { key: '/stock', icon: <DatabaseOutlined />, label: 'Остатки' },
  { key: '/movements', icon: <HistoryOutlined />, label: 'Журнал движений' },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Sider breakpoint="lg" collapsedWidth={0} theme="light">
        <Typography.Title level={4} style={{ padding: '16px 24px', margin: 0 }}>
          WMS
        </Typography.Title>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={MENU_ITEMS}
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
