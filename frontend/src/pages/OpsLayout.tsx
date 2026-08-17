// 运营端容器：坐席台 / 数据看板 / badcase 分析（第三波：Tab 未读角标）
import { useEffect, useState } from 'react'
import { Badge, Tabs } from 'antd'
import { DashboardOutlined, BugOutlined, CustomerServiceOutlined } from '@ant-design/icons'
import TicketDesk from './TicketDesk'
import DataBoard from './DataBoard'
import BadcasePage from './BadcasePage'
import { getTickets } from '../api'

export default function OpsLayout() {
  const [active, setActive] = useState('tickets')
  const [openCount, setOpenCount] = useState(0)

  // 轮询未处理工单数，驱动 Tab 角标（#11）
  useEffect(() => {
    let disposed = false
    const poll = () => {
      getTickets({ page: 1, size: 1, status: 'open' })
        .then((r) => { if (!disposed) setOpenCount(r.total) })
        .catch(() => { /* 忽略 */ })
    }
    poll()
    const timer = setInterval(poll, 30000)
    return () => { disposed = true; clearInterval(timer) }
  }, [])

  return (
    <div style={{ padding: 16 }}>
      <Tabs
        activeKey={active}
        onChange={setActive}
        items={[
          {
            key: 'tickets',
            label: <Badge count={openCount} size="small" offset={[6, -2]}><span><CustomerServiceOutlined /> 人工坐席台</span></Badge>,
            children: active === 'tickets' ? <TicketDesk /> : null,
          },
          { key: 'board', label: <span><DashboardOutlined /> 数据看板</span>, children: active === 'board' ? <DataBoard /> : null },
          { key: 'badcase', label: <span><BugOutlined /> badcase 分析</span>, children: active === 'badcase' ? <BadcasePage /> : null },
        ]}
      />
    </div>
  )
}
