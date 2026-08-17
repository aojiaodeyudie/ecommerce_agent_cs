// 运营端：数据看板（第三波：时间范围筛选；#E4 星级评价统计）
import { useEffect, useState } from 'react'
import { Button, Card, Col, DatePicker, Empty, Progress, Rate, Row, Space, Statistic, Table, Tag, message } from 'antd'
import { getStats } from '../api'
import type { Stats } from '../types'

const { RangePicker } = DatePicker

const INTENT_LABELS: Record<string, string> = {
  escalate: '转人工/投诉', refund: '售后', logistics: '物流', order: '订单',
  coupon: '优惠券', policy: '政策', faq: '常见问题', product: '商品',
  knowledge: '专业知识', chitchat: '闲聊', unknown: '未知',
}

// #E4 星级文案
const STAR_TEXT: Record<number, string> = { 1: '很不满', 2: '不满意', 3: '一般', 4: '满意', 5: '很满意' }

export default function DataBoard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [range, setRange] = useState<[string, string] | null>(null)

  const load = (from?: string, to?: string) => {
    getStats(from, to)
      .then(setStats)
      .catch((e) => message.error((e as Error).message))
  }

  useEffect(() => { load() }, [])

  if (!stats) return <Empty description="加载中…" style={{ marginTop: 80 }} />
  if (stats.total === 0) return <Empty description="该时间范围暂无对话数据，去消费者端聊几句吧～" style={{ marginTop: 80 }} />

  const intentRows = Object.entries(stats.intent_dist).map(([k, v]) => ({
    key: k,
    intent: INTENT_LABELS[k] ?? k,
    count: v,
    percent: Math.round((v / stats.total) * 100),
  }))

  const actionRows = Object.entries(stats.action_dist).map(([k, v]) => ({
    key: k,
    action: k === 'agent' ? 'Agent 智能回复' : k === 'faq' ? 'FAQ 直答' : k === 'escalate' ? '转人工' : k,
    count: v,
    percent: Math.round((v / stats.total) * 100),
  }))

  // #E4 星级分布行（1-5 星）
  const starRows = Array.from({ length: 5 }, (_, i) => {
    const star = i + 1
    const count = stats.star_dist?.[String(star)] ?? 0
    return {
      key: star,
      star,
      text: STAR_TEXT[star],
      count,
      percent: stats.rated_count > 0 ? Math.round((count / stats.rated_count) * 100) : 0,
      bad: star <= 3,
    }
  })
  // 解决情况行
  const solvedRows = Object.entries(stats.solved_dist ?? {}).map(([k, v]) => ({
    key: k,
    solved: k,
    count: v,
  }))

  return (
    <div>
      <Space style={{ marginBottom: 12 }} wrap>
        <RangePicker
          onChange={(_, dateStrings) => {
            if (dateStrings[0] && dateStrings[1]) {
              setRange([dateStrings[0], dateStrings[1]])
              load(dateStrings[0], dateStrings[1])
            } else {
              setRange(null)
              load()
            }
          }}
        />
        {range && <Button size="small" onClick={() => { setRange(null); load() }}>清除筛选</Button>}
      </Space>

      <Row gutter={16}>
        <Col span={4}><Card><Statistic title="总对话数" value={stats.total} /></Card></Col>
        <Col span={4}><Card><Statistic title="转人工率" value={stats.escalate_rate * 100} precision={1} suffix="%" /></Card></Col>
        <Col span={4}><Card><Statistic title="FAQ 直答率" value={stats.faq_hit_rate * 100} precision={1} suffix="%" /></Card></Col>
        <Col span={4}><Card><Statistic title="工具调用次数" value={stats.tool_calls} /></Card></Col>
        {/* #E4 差评统计 */}
        <Col span={4}>
          <Card>
            <Statistic title="已评价" value={stats.rated_count} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="差评数（1-3星）"
              value={stats.bad_count}
              valueStyle={stats.bad_count > 0 ? { color: '#cf1322' } : undefined}
              suffix={`/ ${stats.rated_count}`}
            />
          </Card>
        </Col>
      </Row>
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="差评率"
              value={stats.bad_rate * 100}
              precision={1}
              suffix="%"
              valueStyle={stats.bad_rate > 0.3 ? { color: '#cf1322' } : undefined}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={12}>
          <Card title="意图分布" size="small">
            <Table
              size="small"
              pagination={false}
              dataSource={intentRows}
              columns={[
                { title: '意图', dataIndex: 'intent' },
                { title: '次数', dataIndex: 'count', width: 80 },
                {
                  title: '占比',
                  dataIndex: 'percent',
                  width: 220,
                  render: (p: number) => <Progress percent={p} size="small" />,
                },
              ]}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="路由动作分布" size="small">
            <Table
              size="small"
              pagination={false}
              dataSource={actionRows}
              columns={[
                { title: '动作', dataIndex: 'action' },
                { title: '次数', dataIndex: 'count', width: 80 },
                {
                  title: '占比',
                  dataIndex: 'percent',
                  width: 220,
                  render: (p: number) => <Progress percent={p} size="small" status={p >= 50 ? 'active' : undefined} />,
                },
              ]}
            />
          </Card>
        </Col>
      </Row>

      {/* #E4 星级评价分布 + 解决情况 */}
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={14}>
          <Card title="星级评价分布" size="small" extra={<Tag color="red">1-3 星为差评</Tag>}>
            <Table
              size="small"
              pagination={false}
              dataSource={starRows}
              rowClassName={(r) => (r.bad ? 'bad-star-row' : '')}
              columns={[
                {
                  title: '星级',
                  dataIndex: 'star',
                  width: 130,
                  render: (s: number, r) => (
                    <span>
                      <Rate disabled value={s} style={{ fontSize: 13 }} />
                      <span style={{ marginLeft: 6, color: r.bad ? '#cf1322' : '#333' }}>{r.text}</span>
                    </span>
                  ),
                },
                { title: '次数', dataIndex: 'count', width: 70 },
                {
                  title: '占比',
                  dataIndex: 'percent',
                  width: 200,
                  render: (p: number, r) => (
                    <Progress percent={p} size="small" strokeColor={r.bad ? '#ff4d4f' : undefined} />
                  ),
                },
              ]}
            />
          </Card>
        </Col>
        <Col span={10}>
          <Card title="问题解决情况（已评价）" size="small">
            {solvedRows.length === 0 ? (
              <Empty description="暂无解决情况数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <Table
                size="small"
                pagination={false}
                dataSource={solvedRows}
                columns={[
                  {
                    title: '结果',
                    dataIndex: 'solved',
                    render: (s: string) => (
                      <Tag color={s === '已解决' ? 'green' : 'orange'}>{s === '已解决' ? '✅ 已解决' : '❌ 未解决'}</Tag>
                    ),
                  },
                  { title: '次数', dataIndex: 'count' },
                ]}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
