// 主入口：侧栏区分 消费者端 / 运营端
// #F6：用户切换置于顶部 Header 右上角（与标题持平）
import { useState } from 'react'
import { Avatar, Layout, Menu, Select, Typography } from 'antd'
import {
  MessageOutlined, SettingOutlined, ShopOutlined,
} from '@ant-design/icons'
import ConsumerChat from './pages/ConsumerChat'
import OpsLayout from './pages/OpsLayout'

const { Sider, Content, Header } = Layout

// 模拟用户列表（与后端种子数据 user_id 对应，展示中文名）
const USER_LIST = [
  { id: '1001', name: '张小雅' },
  { id: '1002', name: '李明轩' },
  { id: '1003', name: '王雨桐' },
  { id: '1004', name: '陈晓峰' },
  { id: '1005', name: '刘思琪' },
]

export default function App() {
  const [end, setEnd] = useState<'consumer' | 'ops'>('consumer')
  // #F6 当前用户（消费者端右上角切换，提升到 App 层）
  const [userId, setUserId] = useState<string>('1001')

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="light" width={200}>
        <div style={{ padding: '16px 12px', fontSize: 16, fontWeight: 600 }}>
          🛒 电商智能客服
        </div>
        <Menu
          mode="inline"
          selectedKeys={[end]}
          onClick={({ key }) => setEnd(key as 'consumer' | 'ops')}
          items={[
            { key: 'consumer', icon: <MessageOutlined />, label: '消费者端' },
            { key: 'ops', icon: <SettingOutlined />, label: '运营端' },
          ]}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', display: 'flex', alignItems: 'center' }}>
          <Typography.Text strong>
            {end === 'consumer' ? <span><ShopOutlined /> 消费者端 · 在线客服</span> : '运营端 · 管理后台'}
          </Typography.Text>
          {/* #F6 消费者端：右上角用户切换，与标题持平 */}
          {end === 'consumer' && (
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Avatar size={28} style={{ background: '#52c41a' }}>
                {(USER_LIST.find((u) => u.id === userId)?.name ?? '客').slice(0, 1)}
              </Avatar>
              <Select
                size="small"
                style={{ minWidth: 130 }}
                value={userId}
                onChange={setUserId}
                options={USER_LIST.map((u) => ({ value: u.id, label: u.name }))}
                notFoundContent="无"
              />
            </div>
          )}
        </Header>
        <Content>
          {end === 'consumer' ? <ConsumerChat userId={userId} onUserChange={setUserId} /> : <OpsLayout />}
        </Content>
      </Layout>
    </Layout>
  )
}
