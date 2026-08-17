// 运营端：人工坐席台（第三波：分页/搜索/筛选/自动轮询/坐席回复；软删除）
// #E4：新增"客户差评"视图（1-3 星评价，含星级/是否解决/问题描述）
// #E5：差评支持 单项删除 / 坐席回复 / 一键删除
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Button, Card, Collapse, Empty, Input, List, Modal, Pagination, Popconfirm, Rate, Select, Segmented, Space, Tag, Typography, message,
} from 'antd'
import {
  deleteAllBadRatings, deleteAllOpenTickets, deleteBadRating, deleteTicket,
  getBadRatings, getTickets, replyBadRating, replyTicket, resolveTicket,
} from '../api'
import type { TicketPage } from '../api'
import type { BadRating } from '../types'

const { Search } = Input
const { Text } = Typography

// 星级文案
const STAR_TEXT: Record<number, string> = { 1: '很不满', 2: '不满意', 3: '一般', 4: '满意', 5: '很满意' }

export default function TicketDesk() {
  const [view, setView] = useState<'tickets' | 'ratings'>('tickets')  // #E4 视图切换
  const [data, setData] = useState<TicketPage | null>(null)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [size] = useState(10)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<string>('open')
  // 客户差评（#E4）
  const [badRatings, setBadRatings] = useState<BadRating[]>([])
  const [ratingsLoading, setRatingsLoading] = useState(false)
  // 差评回复弹窗（#E5）
  const [replyTarget, setReplyTarget] = useState<string | null>(null)
  const [replyText, setReplyText] = useState('')
  const [replying, setReplying] = useState(false)
  // 工单回复弹窗
  const [ticketReplyTarget, setTicketReplyTarget] = useState<string | null>(null)
  const [ticketReplyText, setTicketReplyText] = useState('')
  const [ticketReplying, setTicketReplying] = useState(false)
  const loadRef = useRef<() => void>(() => {})

  const load = useCallback(async (p = page, kw = keyword, st = status) => {
    setLoading(true)
    try {
      const res = await getTickets({ page: p, size, keyword: kw || undefined, status: st })
      setData(res)
    } catch (e) {
      message.error((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [page, keyword, status, size])

  // 手动刷新 + 供轮询复用
  loadRef.current = () => load()

  // 首次加载
  useEffect(() => { load() }, [])

  // 客户差评加载（#E4）：切到差评视图或定时刷新时拉取
  const loadBadRatings = useCallback(async () => {
    setRatingsLoading(true)
    try {
      setBadRatings(await getBadRatings(100))
    } catch (e) {
      message.error((e as Error).message)
    } finally {
      setRatingsLoading(false)
    }
  }, [])
  useEffect(() => {
    if (view === 'ratings') loadBadRatings()
  }, [view, loadBadRatings])

  // 自动轮询（30s，#11）：工单 + 差评一起刷新
  useEffect(() => {
    const timer = setInterval(() => {
      loadRef.current()
      if (view === 'ratings') loadBadRatings()
    }, 30000)
    return () => clearInterval(timer)
  }, [view, loadBadRatings])

  const handleSearch = (value: string) => {
    setKeyword(value)
    setPage(1)
    load(1, value, status)
  }

  const handleStatus = (value: string) => {
    setStatus(value)
    setPage(1)
    load(1, keyword, value)
  }

  const handleResolve = async (id: string) => {
    try {
      await resolveTicket(id)
      message.success(`工单 ${id} 已解决`)
      load()
    } catch (e) {
      message.error((e as Error).message)
    }
  }

  // 坐席回复工单（#12）：追加客服消息到会话，用户下次访问可见
  const submitTicketReply = async () => {
    if (!ticketReplyTarget || !ticketReplyText.trim()) return
    setTicketReplying(true)
    try {
      await replyTicket(ticketReplyTarget, ticketReplyText.trim())
      message.success('回复已写入会话')
      setTicketReplyTarget(null)
      setTicketReplyText('')
      load()
    } catch (e) {
      message.error((e as Error).message)
    } finally {
      setTicketReplying(false)
    }
  }

  // 软删除单条工单
  const handleDelete = async (id: string) => {
    try {
      await deleteTicket(id)
      message.success(`工单 ${id} 已删除`)
      load()
    } catch (e) {
      message.error((e as Error).message)
    }
  }

  // 一键删除全部待处理工单
  const handleDeleteAll = async () => {
    try {
      const res = await deleteAllOpenTickets()
      message.success(`已删除 ${res.deleted_count} 条待处理工单`)
      load()
    } catch (e) {
      message.error((e as Error).message)
    }
  }

  // ---- #E5 差评操作 ----

  // 删除单条差评
  const handleDeleteRating = async (chatId: string) => {
    try {
      await deleteBadRating(chatId)
      message.success('差评已删除')
      loadBadRatings()
    } catch (e) {
      message.error((e as Error).message)
    }
  }

  // 一键删除全部差评
  const handleDeleteAllRatings = async () => {
    try {
      const res = await deleteAllBadRatings()
      message.success(`已删除 ${res.deleted_count} 条差评`)
      loadBadRatings()
    } catch (e) {
      message.error((e as Error).message)
    }
  }

  // 坐席回复差评：写入差评记录 + 追加到用户会话
  const submitRatingReply = async () => {
    if (!replyTarget || !replyText.trim()) return
    setReplying(true)
    try {
      await replyBadRating(replyTarget, replyText.trim())
      message.success('回复已发送，用户可在会话中看到')
      setReplyTarget(null)
      setReplyText('')
      loadBadRatings()
    } catch (e) {
      message.error((e as Error).message)
    } finally {
      setReplying(false)
    }
  }

  const total = data?.total ?? 0
  const items = data?.items ?? []

  return (
    <div>
      {/* #E4 视图切换：待处理工单 / 客户差评 */}
      <Segmented
        style={{ marginBottom: 12 }}
        value={view}
        onChange={(v) => setView(v as 'tickets' | 'ratings')}
        options={[
          { label: `📋 待处理工单（${total}）`, value: 'tickets' },
          { label: `⭐ 客户差评（${badRatings.length}）`, value: 'ratings' },
        ]}
      />

      {view === 'tickets' && (
        <>
      <Space style={{ marginBottom: 12 }} wrap>
        <Search
          placeholder="搜索工单号 / 用户ID / 原因"
          allowClear
          style={{ width: 280 }}
          onSearch={handleSearch}
        />
        <Select
          value={status}
          style={{ width: 140 }}
          onChange={handleStatus}
          options={[
            { value: 'open', label: '待处理' },
            { value: 'processing', label: '处理中' },
            { value: 'resolved', label: '已解决' },
            { value: 'all', label: '全部' },
          ]}
        />
        <Button onClick={() => load()} loading={loading}>刷新</Button>
        <Tag>共 {total} 条</Tag>
        {/* 一键删除全部待处理（软删除） */}
        <Popconfirm
          title="删除全部待处理工单？"
          description="将软删除当前所有待处理工单（数据保留，可从列表移除）。此操作不可撤销。"
          okText="确认删除"
          cancelText="取消"
          okButtonProps={{ danger: true }}
          onConfirm={handleDeleteAll}
        >
          <Button danger>一键删除全部待处理</Button>
        </Popconfirm>
      </Space>

      {items.length === 0 && !loading ? (
        <Empty description="暂无工单" style={{ marginTop: 60 }} />
      ) : (
        <>
          <List
            loading={loading}
            dataSource={items}
            renderItem={(t) => (
              <Card
                key={t.ticket_id}
                style={{ marginBottom: 12 }}
                title={<span>工单 {t.ticket_id} <Tag color={t.status === 'open' ? 'red' : t.status === 'processing' ? 'orange' : 'green'}>{t.status === 'open' ? '待处理' : t.status === 'processing' ? '处理中' : '已解决'}</Tag></span>}
                extra={
                  <Space>
                    <Button size="small" onClick={() => { setTicketReplyTarget(t.ticket_id); setTicketReplyText('') }}>回复</Button>
                    {t.status !== 'resolved' && (
                      <Button size="small" type="primary" onClick={() => handleResolve(t.ticket_id)}>标记已解决</Button>
                    )}
                    {/* 删除单条（软删除） */}
                    <Popconfirm
                      title="删除该工单？"
                      description="软删除：工单将从列表消失（数据保留）。"
                      okText="删除"
                      cancelText="取消"
                      okButtonProps={{ danger: true }}
                      onConfirm={() => handleDelete(t.ticket_id)}
                    >
                      <Button size="small" danger>删除</Button>
                    </Popconfirm>
                  </Space>
                }
              >
                <p>👤 用户：{t.user_id ?? '-'}　🔗 会话：{t.session_id ?? '-'}　🕐 {t.created_at}</p>
                <p>📝 原因：{t.reason}</p>
                {t.transcript.length > 0 && (
                  <Collapse
                    size="small"
                    items={[{
                      key: 't',
                      label: `💬 完整对话记录（${t.transcript.length} 条）`,
                      children: (
                        <div>
                          {t.transcript.map((m, i) => (
                            <p key={i} style={{ marginBottom: 4 }}>
                              <Tag color={m.role === 'user' ? 'blue' : 'green'}>{m.role === 'user' ? '用户' : '客服'}</Tag>
                              {m.content}
                            </p>
                          ))}
                        </div>
                      ),
                    }]}
                  />
                )}
              </Card>
            )}
          />
          <div style={{ textAlign: 'center', marginTop: 12 }}>
            <Pagination
              current={page}
              pageSize={size}
              total={total}
              showSizeChanger={false}
              onChange={(p) => { setPage(p); load(p, keyword, status) }}
            />
          </div>
        </>
      )}
      </>
      )}

      {/* #E4 客户差评视图：1-3 星评价列表（#E5 支持删除/回复/一键删除） */}
      {view === 'ratings' && (
        <div>
          <Space style={{ marginBottom: 12 }} wrap>
            <Button size="small" onClick={loadBadRatings} loading={ratingsLoading}>刷新差评</Button>
            <Tag color="red">1-3 星为差评，共 {badRatings.length} 条</Tag>
            <Text type="secondary" style={{ fontSize: 12 }}>
              差评来自客户"评价本次服务"打分 ≤3 星，请及时跟进处理
            </Text>
            {/* 一键删除全部差评（#E5） */}
            <Popconfirm
              title="删除全部差评？"
              description={`将删除全部 ${badRatings.length} 条差评记录（数据不可恢复）。`}
              okText="确认删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={handleDeleteAllRatings}
            >
              <Button danger size="small">一键删除全部差评</Button>
            </Popconfirm>
          </Space>
          {badRatings.length === 0 && !ratingsLoading ? (
            <Empty description="暂无差评（1-3 星）" style={{ marginTop: 60 }} />
          ) : (
            <List
              loading={ratingsLoading}
              dataSource={badRatings}
              renderItem={(r) => (
                <Card
                  key={r.chat_id}
                  style={{ marginBottom: 12 }}
                  title={
                    <span>
                      <Rate disabled value={r.rating} style={{ fontSize: 14 }} />
                      <Tag color="red" style={{ marginLeft: 8 }}>
                        {STAR_TEXT[r.rating]}（{r.rating}星）
                      </Tag>
                      {r.solved && (
                        <Tag color={r.solved === '已解决' ? 'green' : 'orange'}>
                          {r.solved === '已解决' ? '✅ 已解决' : '❌ 未解决'}
                        </Tag>
                      )}
                      {r.rating_reply && (
                        <Tag color="blue">💬 已回复 {r.rating_replied_at ?? ''}</Tag>
                      )}
                    </span>
                  }
                  extra={
                    <Space>
                      <Button size="small" type="primary" ghost onClick={() => { setReplyTarget(r.chat_id); setReplyText('') }}>
                        回复
                      </Button>
                      <Popconfirm
                        title="删除该差评？"
                        description="将删除该条差评记录（数据不可恢复）。"
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                        onConfirm={() => handleDeleteRating(r.chat_id)}
                      >
                        <Button size="small" danger>删除</Button>
                      </Popconfirm>
                    </Space>
                  }
                >
                  <p>👤 用户：{r.user_id ?? '-'}　🔗 会话：{r.session_id ?? '-'}　🕐 {r.ts}</p>
                  <p>💬 客户提问：{r.query || '-'}</p>
                  {r.reason && (
                    <p style={{ color: '#cf1322' }}>📝 问题描述：{r.reason}</p>
                  )}
                  {r.rating_reply ? (
                    <div style={{ marginTop: 8, padding: '6px 10px', background: '#f0f7ff', borderRadius: 6 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>🤝 坐席回复（{r.rating_replied_at}）：</Text>
                      <div style={{ whiteSpace: 'pre-wrap', marginTop: 2 }}>{r.rating_reply}</div>
                    </div>
                  ) : null}
                  {r.reply && (
                    <Collapse
                      size="small"
                      style={{ marginTop: 8 }}
                      items={[{
                        key: 'reply',
                        label: '🤖 客服当时的回复',
                        children: <div style={{ whiteSpace: 'pre-wrap' }}>{r.reply}</div>,
                      }]}
                    />
                  )}
                </Card>
              )}
            />
          )}
        </div>
      )}

      {/* 工单回复弹窗 */}
      <Modal
        title={`回复工单 ${ticketReplyTarget ?? ''}`}
        open={ticketReplyTarget !== null}
        onOk={submitTicketReply}
        onCancel={() => setTicketReplyTarget(null)}
        okText="发送回复"
        cancelText="取消"
        confirmLoading={ticketReplying}
      >
        <p style={{ color: '#999', fontSize: 12 }}>
          回复将作为客服消息写入该用户的会话（用户下次访问时可见）。当前不做实时推送。
        </p>
        <Input.TextArea
          rows={4}
          value={ticketReplyText}
          onChange={(e) => setTicketReplyText(e.target.value)}
          placeholder="请输入对用户的回复…"
        />
      </Modal>

      {/* 差评回复弹窗（#E5） */}
      <Modal
        title={`回复差评 ${replyTarget ?? ''}`}
        open={replyTarget !== null}
        onOk={submitRatingReply}
        onCancel={() => setReplyTarget(null)}
        okText="发送回复"
        cancelText="取消"
        confirmLoading={replying}
      >
        <p style={{ color: '#999', fontSize: 12 }}>
          回复将写入差评记录并追加到该用户的会话（消费者端下次访问时可见）。
        </p>
        <Input.TextArea
          rows={4}
          value={replyText}
          onChange={(e) => setReplyText(e.target.value)}
          placeholder="请针对客户差评问题回复…"
        />
      </Modal>
    </div>
  )
}
