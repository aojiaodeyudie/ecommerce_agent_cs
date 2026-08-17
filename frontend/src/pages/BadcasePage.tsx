// 运营端：badcase 分析（含 FAQ 盲区一键入库 #16a + 加载更多 #17）
import { useEffect, useState } from 'react'
import {
  Button, Card, Empty, Form, Input, List, Modal, Tag, message,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { addFaq, getBadcase } from '../api'
import type { Badcase, ChatLogEntry } from '../types'

function EntryList({ title, color, entries, emptyText, extraRender, visibleCount, onLoadMore }: {
  title: string
  color: string
  entries: ChatLogEntry[]
  emptyText: string
  extraRender?: (entry: ChatLogEntry) => React.ReactNode
  visibleCount: number
  onLoadMore?: () => void
}) {
  return (
    <Card title={<span>{title} <Tag color={color}>{entries.length}</Tag></span>} size="small" style={{ marginBottom: 16 }}>
      {entries.length === 0 ? (
        <Empty description={emptyText} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <>
          <List
            size="small"
            dataSource={entries.slice(0, visibleCount)}
            renderItem={(r, i) => (
              <List.Item
                actions={extraRender ? [extraRender(r)] : undefined}
              >
                <List.Item.Meta
                  title={<span>#{i + 1} {r.query ?? '(空)'}</span>}
                description={
                  <span>
                    <Tag>{r.ts ?? '-'}</Tag>
                    {r.intent && <Tag color="blue">{r.intent}</Tag>}
                    {r.ticket_id && <Tag color="red">工单 {r.ticket_id}</Tag>}
                    <div style={{ color: '#999' }}>回复：{r.reply ? String(r.reply).slice(0, 60) : '(空)'}</div>
                  </span>
                }
              />
            </List.Item>
          )}
        />
        {/* 加载更多（第四波 #17） */}
        {entries.length > visibleCount && (
          <div style={{ textAlign: 'center', marginTop: 8 }}>
            <Button size="small" onClick={onLoadMore}>
              加载更多（还有 {entries.length - visibleCount} 条）
            </Button>
          </div>
        )}
        </>
      )}
    </Card>
  )
}

export default function BadcasePage() {
  const [data, setData] = useState<Badcase | null>(null)
  const [faqModal, setFaqModal] = useState<{ open: boolean; question: string }>({ open: false, question: '' })
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)
  const [visible, setVisible] = useState<Record<string, number>>({
    escalations: 10, faq_misses: 10, empty_replies: 10,
  }) // 每类独立显示条数（加载更多 #17）
  const VISIBLE_STEP = 10

  const loadMore = (key: string) => setVisible((prev) => ({ ...prev, [key]: prev[key] + VISIBLE_STEP }))

  const load = () => {
    getBadcase().then(setData).catch((e) => message.error((e as Error).message))
  }

  useEffect(() => { load() }, [])

  // FAQ 盲区一键入库（#16a）：预填问题，运营补答案后提交
  const openFaqModal = (entry: ChatLogEntry) => {
    setFaqModal({ open: true, question: entry.query ?? '' })
    form.setFieldsValue({ question: entry.query ?? '', answer: '', keywords: '' })
  }

  const submitFaq = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)
      await addFaq({
        question: values.question,
        answer: values.answer,
        keywords: values.keywords || '',
        category: 'general',
      })
      message.success('已加入 FAQ 库')
      setFaqModal({ open: false, question: '' })
      form.resetFields()
      load() // 刷新：该盲区消失
    } catch (e) {
      message.error((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  if (!data) return <Empty description="加载中…" style={{ marginTop: 80 }} />
  if (!data.escalations.length && !data.faq_misses.length && !data.empty_replies.length) {
    return <Empty description="暂无 badcase 数据，产生一些对话后再来看～" style={{ marginTop: 80 }} />
  }

  return (
    <div>
      <EntryList
        title="🙋 转人工诉求（投诉/不满，需关注）"
        color="red"
        entries={data.escalations}
        emptyText="暂无转人工记录"
        visibleCount={visible.escalations}
        onLoadMore={() => loadMore('escalations')}
      />
      <EntryList
        title="📚 FAQ 盲区候选（这些常见问题没被 FAQ 覆盖，建议补库）"
        color="orange"
        entries={data.faq_misses}
        emptyText="暂无 FAQ 盲区"
        visibleCount={visible.faq_misses}
        onLoadMore={() => loadMore('faq_misses')}
        extraRender={(entry) => (
          <Button size="small" type="primary" ghost icon={<PlusOutlined />} onClick={() => openFaqModal(entry)}>
            加入 FAQ
          </Button>
        )}
      />
      <EntryList
        title="⚠️ 异常回复候选（空/过短，可能生成失败）"
        color="purple"
        entries={data.empty_replies}
        emptyText="暂无异常回复"
        visibleCount={visible.empty_replies}
        onLoadMore={() => loadMore('empty_replies')}
      />

      {/* 加入 FAQ 弹窗 */}
      <Modal
        title="📚 加入 FAQ 库"
        open={faqModal.open}
        onOk={submitFaq}
        onCancel={() => setFaqModal({ open: false, question: '' })}
        okText="提交"
        cancelText="取消"
        confirmLoading={submitting}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item name="question" label="问题" rules={[{ required: true, message: '请输入问题' }]}>
            <Input placeholder="用户常问的问题" />
          </Form.Item>
          <Form.Item name="answer" label="答案" rules={[{ required: true, message: '请输入答案' }]}>
            <Input.TextArea rows={4} placeholder="标准答案（供 FAQ 直答返回）" />
          </Form.Item>
          <Form.Item name="keywords" label="命中关键词（可选，逗号分隔）">
            <Input placeholder="例如：退货,退款,退换" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
