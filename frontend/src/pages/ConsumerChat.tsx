// 消费者端：聊天界面（SSE 流式输出 + 停止生成 + Markdown 渲染 + 满意度评价 + 会话恢复 + 会话切换）
// 输入区功能（#E2）：发送图片 / 发表情 / 本次服务评价（#E3 星级）
// #F2：左侧对话对象栏（智能客服 + 商家 A/B/C），各对象独立会话
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Avatar, Button, Input, Modal, Popover, Radio, Rate, Select, Space, Tag, Typography, Upload, message,
} from 'antd'
import {
  LikeOutlined, DislikeOutlined, PlusOutlined, PictureOutlined, SmileOutlined, StarOutlined,
  RobotOutlined, ThunderboltOutlined, HomeOutlined, CloudOutlined,
  ShoppingOutlined, ShoppingCartOutlined, ReadOutlined,
} from '@ant-design/icons'
import type { UploadProps } from 'antd'
import { chatStream, getFaqs, getHistory, getSessions, rate, uploadImage } from '../api'
import type { ChatMessage, SessionItem } from '../types'
import MessageBubble from '../components/MessageBubble'

const { Text } = Typography

// 快捷问题兜底（动态获取失败时使用）
const FALLBACK_QUICK_QUESTIONS = ['X30多少钱', '查我的订单', '快递到哪了', '怎么退货', '转人工']

// #F4 模拟用户列表（右上角切换；与后端种子数据 user_id 对应，展示中文名）
const USER_LIST = [
  { id: '1001', name: '张小雅' },
  { id: '1002', name: '李明轩' },
  { id: '1003', name: '王雨桐' },
  { id: '1004', name: '陈晓峰' },
  { id: '1005', name: '刘思琪' },
]
const DEFAULT_USER = USER_LIST[0]

// 差评原因选项
const DISLIKE_REASONS = ['回答不准确', '回答太慢', '没解决我的问题', '其他']

// #F2 对话对象定义：智能客服 + 6 家商家（各对象独立会话）
interface ChatTarget {
  key: string
  name: string
  desc: string
  icon: React.ReactNode
  bg: string
  welcome: string
  /** #F8 商家专属快捷语；ai 用 null 表示走 FAQ 动态获取 */
  quick: string[] | null
}
const CHAT_TARGETS: ChatTarget[] = [
  {
    key: 'ai',
    name: '智能客服',
    desc: '官方 AI 助手',
    icon: <RobotOutlined />,
    bg: 'linear-gradient(135deg, #4f8cff, #7a5cff)',
    welcome: '👋 您好！我是官方智能客服，可以帮您查询商品、订单、物流，处理退换货，转接人工等～',
    quick: null,
  },
  {
    key: 'shop_a',
    name: '星辉数码旗舰店',
    desc: '数码 3C · 手机电脑',
    icon: <ThunderboltOutlined />,
    bg: 'linear-gradient(135deg, #fa8c16, #f5222d)',
    welcome: '欢迎光临星辉数码旗舰店！本店主营数码 3C 产品，手机、电脑、配件一应俱全，请问有什么可以帮您？',
    quick: ['星辉S10手机多少钱', '轻羽Air轻薄本配置', '声浪Pro耳机价格', '疾风T9游戏本有货吗', '转人工'],
  },
  {
    key: 'shop_b',
    name: '蓝鲸家电专卖店',
    desc: '大家电 · 空调冰洗',
    icon: <HomeOutlined />,
    bg: 'linear-gradient(135deg, #13c2c2, #1677ff)',
    welcome: '欢迎光临蓝鲸家电专卖店！本店主营大家电，空调、冰箱、洗衣机等，很高兴为您服务～',
    quick: ['蓝鲸1.5匹空调多少钱', 'X30扫地机器人价格', '冰箱送货上门吗', '洗衣机保修几年', '转人工'],
  },
  {
    key: 'shop_c',
    name: '云端生活馆',
    desc: '生活电器 · 厨房小家电',
    icon: <CloudOutlined />,
    bg: 'linear-gradient(135deg, #722ed1, #eb2f96)',
    welcome: '欢迎光临云端生活馆！本店主营生活电器与厨房小家电，请问需要什么帮助？',
    quick: ['破壁机多少钱', '空气炸锅怎么用', '电饭煲容量怎么选', '咖啡机有食谱吗', '转人工'],
  },
  {
    key: 'shop_d',
    name: '绿野家居旗舰店',
    desc: '家居日用 · 床品收纳',
    icon: <ShoppingOutlined />,
    bg: 'linear-gradient(135deg, #52c41a, #389e0d)',
    welcome: '欢迎光临绿野家居旗舰店！本店主营家居日用，床品、收纳、清洁用品齐全，有什么可以帮您？',
    quick: ['四件套多少钱', '乳胶枕有吗', '收纳箱多大合适', '窗帘遮光效果好吗', '转人工'],
  },
  {
    key: 'shop_e',
    name: '鲜橙生鲜超市',
    desc: '生鲜果蔬 · 肉禽蛋奶',
    icon: <ShoppingCartOutlined />,
    bg: 'linear-gradient(135deg, #faad14, #d46b08)',
    welcome: '欢迎光临鲜橙生鲜超市！本店主营生鲜果蔬、肉禽蛋奶，当日达新鲜到家，需要什么？',
    quick: ['车厘子多少钱', '草莓是当天到的吗', '三文鱼怎么保存', '鸡蛋多少枚一盒', '转人工'],
  },
  {
    key: 'shop_f',
    name: '悦读书香书店',
    desc: '图书文创 · 文具办公',
    icon: <ReadOutlined />,
    bg: 'linear-gradient(135deg, #1677ff, #531dab)',
    welcome: '欢迎光临悦读书香书店！本店主营图书、文创与文具，找书请随时问我～',
    quick: ['三体多少钱', '小王子有双语版吗', '中性笔多少钱', '故宫书签有货吗', '转人工'],
  },
]

// 星级评价文案（#E3）：1很不满 / 2不满意 / 3一般 / 4满意 / 5很满意
const STAR_TIPS: Record<number, string> = {
  1: '😞 很不满',
  2: '😕 不满意',
  3: '😐 一般',
  4: '😊 满意',
  5: '🥰 很满意',
}

// 常用表情（点击插入输入框）
const EMOJIS = ['😀', '😄', '😁', '😊', '🙂', '😉', '😍', '🥰', '😘', '😜', '🤪', '🤔', '😅', '😂', '🤣', '😭', '😢', '😡', '👍', '👎', '👏', '🙏', '💪', '🤝', '🎉', '❤️', '💔', '⭐', '🔥', '✅', '❌', '❓', '❗', '💡', '😴', '🤗', '😇', '🥳']

function newSessionId(): string {
  return `S${Math.random().toString(16).slice(2, 10).toUpperCase()}`
}

// #F2 各对象会话 ID：localStorage 持久化（#F4 按用户区分，切换用户互不干扰）
function getTargetSid(userId: string, key: string): string {
  if (key === 'ai') {
    // 智能客服：优先 URL ?sid=（兼容旧逻辑）
    const params = new URLSearchParams(window.location.search)
    const urlSid = params.get('sid')
    if (urlSid) return urlSid
  }
  const storeKey = `cs_sid_${userId}_${key}`
  const stored = localStorage.getItem(storeKey)
  if (stored) return stored
  const created = newSessionId()
  localStorage.setItem(storeKey, created)
  return created
}

function fmtTime(d: Date): string {
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

interface ConsumerChatProps {
  /** #F6 当前用户（App 顶层 Header 切换，提升为受控 props） */
  userId: string
  onUserChange: (uid: string) => void
}

export default function ConsumerChat({ userId, onUserChange }: ConsumerChatProps) {
  // #F2 当前对话对象
  const [activeTarget, setActiveTarget] = useState<string>('ai')
  // 各对象独立的会话 ID（ref 保证 send 稳定引用；#F4 按用户生成）
  const sidByTarget = useRef<Record<string, string>>(
    Object.fromEntries(CHAT_TARGETS.map((t) => [t.key, getTargetSid(userId, t.key)])),
  )
  // userId 的 ref 镜像：send 空依赖闭包安全
  const userIdRef = useRef(userId)
  useEffect(() => { userIdRef.current = userId }, [userId])
  // 各对象独立的消息缓存（切换对象时保留各自上下文）
  const [messagesByTarget, setMessagesByTarget] = useState<Record<string, ChatMessage[]>>({})
  // activeTarget 的 ref 镜像：setMessages 保持稳定引用（send 空依赖闭包安全）
  const activeTargetRef = useRef(activeTarget)
  useEffect(() => { activeTargetRef.current = activeTarget }, [activeTarget])
  const messages = messagesByTarget[activeTarget] ?? []
  const setMessages = useCallback((updater: (prev: ChatMessage[]) => ChatMessage[]) => {
    setMessagesByTarget((prevMap) => {
      const key = activeTargetRef.current
      const cur = prevMap[key] ?? []
      const next = updater(cur)
      return { ...prevMap, [key]: next }
    })
  }, [])
  const currentSid = sidByTarget.current[activeTarget]
  const currentTarget = CHAT_TARGETS.find((t) => t.key === activeTarget) ?? CHAT_TARGETS[0]

  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [rated, setRated] = useState<Record<string, 1 | -1>>({})
  const [quickQuestions, setQuickQuestions] = useState<string[]>(FALLBACK_QUICK_QUESTIONS)
  const [dislikeTarget, setDislikeTarget] = useState<string | null>(null) // 差评弹窗目标 chat_id
  const [dislikeReason, setDislikeReason] = useState<string>(DISLIKE_REASONS[0])
  const [dislikeOther, setDislikeOther] = useState('') // "其他"原因输入（问题 D）
  const [sessions, setSessions] = useState<SessionItem[]>([]) // 历史会话列表（第四波）
  // 本次服务评价弹窗（#E3 星级）：星级 + 是否解决 + 问题描述
  const [rateModalOpen, setRateModalOpen] = useState(false)
  const [rateStars, setRateStars] = useState(0)             // 1~5 星，0=未选
  const [rateSolved, setRateSolved] = useState<string | null>(null)  // 已解决 / 未解决
  const [rateDesc, setRateDesc] = useState('')              // 问题描述（1-3 星时显示）
  const [rateTargetChat, setRateTargetChat] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  // #F8 当前快捷语：智能客服走 FAQ 动态（quickQuestions），商家用各自定制
  const quickQuestionsToShow = currentTarget.quick ?? quickQuestions

  // 加载当前对象历史（#F2：切换对象时加载各自会话）
  const loadTargetHistory = useCallback((key: string, sid: string) => {
    getHistory(sid)
      .then((h) => {
        setMessagesByTarget((prev) => ({ ...prev, [key]: h.messages }))
      })
      .catch(() => message.error('加载会话历史失败'))
  }, [])

  // 首次加载（智能客服历史；商家对象缓存为空时展示欢迎语）
  useEffect(() => {
    loadTargetHistory('ai', sidByTarget.current.ai)
  }, [loadTargetHistory])

  // 切换对话对象（#F2）
  const switchTarget = (key: string) => {
    if (key === activeTarget) return
    abortRef.current?.abort() // 停止当前对象的生成
    setActiveTarget(key)
    setRated({})
    setStreaming(false)
    // 若该对象尚无缓存，从后端加载其会话历史
    if (!messagesByTarget[key]) {
      loadTargetHistory(key, sidByTarget.current[key])
    }
    // 滚动到底部
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
  }

  // 动态快捷问题（第二波 #3）：从 FAQ 取前 5 条；失败回退硬编码
  useEffect(() => {
    getFaqs()
      .then((faqs) => {
        const qs = faqs.slice(0, 5).map((f) => f.question).filter(Boolean)
        if (qs.length) setQuickQuestions(qs)
      })
      .catch(() => { /* 保持兜底问题 */ })
  }, [])

  // 历史会话列表（第四波，#F4 按当前用户加载）
  const refreshSessions = useCallback(() => {
    getSessions(userIdRef.current)
      .then((res) => setSessions(res.items))
      .catch(() => { /* 忽略 */ })
  }, [])
  useEffect(() => { refreshSessions() }, [refreshSessions])

  // #F4/#F6 切换用户：Header 改变 userId prop 后，此处重置所有对话对象会话
  const prevUserIdRef = useRef(userId)
  useEffect(() => {
    const prev = prevUserIdRef.current
    prevUserIdRef.current = userId
    if (prev === userId) return // 首次挂载不重置
    abortRef.current?.abort()
    setActiveTarget('ai')
    setMessagesByTarget({})
    setRated({})
    setStreaming(false)
    // 为该用户重新生成各对象会话 ID
    sidByTarget.current = Object.fromEntries(
      CHAT_TARGETS.map((t) => [t.key, getTargetSid(userId, t.key)]),
    )
    loadTargetHistory('ai', sidByTarget.current.ai)
    refreshSessions()
    message.success(`已切换为 ${USER_LIST.find((u) => u.id === userId)?.name ?? userId}`)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId])

  // 切换会话（第四波）：加载目标会话历史（当前对话对象内）
  const switchSession = (targetSid: string) => {
    if (targetSid === currentSid) return
    abortRef.current?.abort()
    sidByTarget.current[activeTarget] = targetSid
    const params = new URLSearchParams(window.location.search)
    params.set('sid', targetSid)
    window.history.replaceState(null, '', `?${params.toString()}`)
    getHistory(targetSid)
      .then((h) => {
        setMessagesByTarget((prev) => ({ ...prev, [activeTarget]: h.messages }))
        setRated({})
      })
      .catch(() => message.error('加载会话失败'))
  }

  // 新建会话（第四波）：重置当前对话对象会话
  const createNewSession = () => {
    abortRef.current?.abort()
    const created = newSessionId()
    sidByTarget.current[activeTarget] = created
    const params = new URLSearchParams(window.location.search)
    params.set('sid', created)
    window.history.replaceState(null, '', `?${params.toString()}`)
    setMessages(() => [])
    setRated({})
    refreshSessions()
  }

  // 组件卸载时取消进行中的请求（防泄漏）
  useEffect(() => {
    return () => abortRef.current?.abort()
  }, [])

  // 自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 停止生成（#1）
  const stop = useCallback(() => abortRef.current?.abort(), [])

  // streamingRef：ref 永远跟随 state（单点真相，无论 send/stop/catch 哪个路径改 state 都同步）
  const streamingRef = useRef(false)
  useEffect(() => { streamingRef.current = streaming }, [streaming])

  // send 引用永久稳定（空依赖）：读 streamingRef 而非 streaming state（C+E 修复）
  const send = useCallback(async (text: string) => {
    const content = text.trim()
    if (!content || streamingRef.current) return
    // 取消上一次未完成的请求
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const now = fmtTime(new Date())
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content, ts: now }])
    setMessages((prev) => [...prev, { role: 'assistant', content: '', ts: now }])
    setStreaming(true)
    const sid = sidByTarget.current[activeTargetRef.current]
    try {
      // #F9 携带当前对话商家（ai=智能客服全店）
      const shopId = activeTargetRef.current === 'ai' ? undefined : activeTargetRef.current
      for await (const ev of chatStream(content, sid, userIdRef.current, controller.signal, shopId)) {
        if (ev.event === 'intent') {
          // 可在此显示"思考中"状态
        } else if (ev.event === 'token') {
          const textChunk = String(ev.data)
          if (textChunk.startsWith('[思考]')) continue // 过滤工具调用痕迹
          // 不可变更新（修复：直接 mutate 在 StrictMode 双调用 updater 下内容会翻倍）
          setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last && last.role === 'assistant') {
              next[next.length - 1] = { ...last, content: last.content + textChunk }
            }
            return next
          })
        } else if (ev.event === 'done') {
          const d = ev.data as { reply: string; chat_id: string; session_id: string }
          sidByTarget.current[activeTargetRef.current] = d.session_id
          const params = new URLSearchParams(window.location.search)
          params.set('sid', d.session_id)
          window.history.replaceState(null, '', `?${params.toString()}`)
          setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            next[next.length - 1] = { ...last, content: d.reply, chat_id: d.chat_id }
            return next
          })
          refreshSessions() // 会话已更新，刷新历史会话列表
        } else if (ev.event === 'error') {
          message.error(`出错：${JSON.stringify(ev.data)}`)
          // 健壮性：移除空占位消息，不留空气泡
          setMessages((prev) => {
            const next = [...prev]
            if (next.length && next[next.length - 1].role === 'assistant' && !next[next.length - 1].content) {
              next.pop()
            }
            return next
          })
        }
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') {
        // 用户主动停止：保留已生成的部分内容，不报错
      } else {
        message.error(`对话失败：${(e as Error).message}`)
        setMessages((prev) => {
          const next = [...prev]
          if (next.length && next[next.length - 1].role === 'assistant' && !next[next.length - 1].content) {
            next.pop()
          }
          return next
        })
      }
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }, [])

  // 满意度评价：好评直接提交；差评弹窗选原因后提交（第二波 #5）
  const handleRate = async (chatId: string, rating: 1 | -1, reason?: string) => {
    try {
      await rate(chatId, rating, reason)
      setRated((prev) => ({ ...prev, [chatId]: rating }))
      message.success(rating === 1 ? '感谢好评！' : '感谢反馈，我们会改进')
    } catch (e) {
      message.error((e as Error).message)
    }
  }

  const submitDislike = () => {
    if (!dislikeTarget) return
    // "其他"时附带自定义输入（问题 D）
    const reason = dislikeReason === '其他'
      ? (dislikeOther.trim() ? `其他：${dislikeOther.trim()}` : '其他')
      : dislikeReason
    handleRate(dislikeTarget, -1, reason)
    setDislikeTarget(null)
    setDislikeOther('')
  }

  // ---- 输入区三功能（#E2）----

  // 1) 发送图片：上传后以 Markdown 图片形式作为消息发送
  const handleSendImage: UploadProps['beforeUpload'] = async (file) => {
    const isImage = file.type.startsWith('image/')
    if (!isImage) {
      message.error('仅支持图片文件（png/jpg/gif/webp 等）')
      return Upload.LIST_IGNORE
    }
    if (file.size > 5 * 1024 * 1024) {
      message.error('图片大小不能超过 5MB')
      return Upload.LIST_IGNORE
    }
    try {
      const { url } = await uploadImage(file)
      await send(`![图片](${url})`)
      message.success('图片已发送')
    } catch (e) {
      message.error(`图片上传失败：${(e as Error).message}`)
    }
    return Upload.LIST_IGNORE // 阻止 antd 默认上传行为（已手动上传）
  }

  // 2) 表情：点击插入输入框
  const insertEmoji = (emoji: string) => {
    setInput((prev) => prev + emoji)
  }

  // 3) 本次服务评价（#E3 星级）：取当前会话最后一条 AI 回复的 chat_id 提交评价
  const openServiceRate = () => {
    // 倒序找最后一条 assistant 且有 chat_id 的消息
    const lastAi = [...messages].reverse().find((m) => m.role === 'assistant' && m.chat_id)
    if (!lastAi?.chat_id) {
      message.info('请先与客服对话，再对本次服务进行评价～')
      return
    }
    setRateStars(0)
    setRateSolved(null)
    setRateDesc('')
    setRateModalOpen(true)
    setRateTargetChat(lastAi.chat_id)
  }

  const submitServiceRate = () => {
    if (!rateTargetChat) return
    if (rateStars < 1 || rateStars > 5) {
      message.warning('请先选择星级（1~5 星）')
      return
    }
    if (!rateSolved) {
      message.warning('请选择问题是否已解决')
      return
    }
    // 1-3 星附带问题描述；4-5 星仅提交星级 + 是否解决
    const desc = rateStars <= 3 && rateDesc.trim() ? rateDesc.trim() : undefined
    rate(rateTargetChat, rateStars, rateSolved, desc)
      .then(() => {
        setRateModalOpen(false)
        message.success('感谢您此次评价！🌟')
      })
      .catch((e) => message.error(`评价提交失败：${(e as Error).message}`))
  }

  return (
    // #F3 统一大卡片：左侧对象栏 + 右侧聊天区一体，背景一致；加宽往左拉伸
    // #F6 用户切换已提升至 App 顶层 Header（与"消费者端 · 在线客服"持平），此处不再重复
    <div style={{ maxWidth: 1160, margin: '0 auto', padding: '12px 16px 16px', height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
      {/* 主卡片：左侧对象栏 + 右侧聊天区 */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0, background: '#fff', border: '1px solid #f0f0f0', borderRadius: 10, overflow: 'hidden' }}>
      {/* #F2 左侧对话对象栏（与大卡片一体，浅灰底 + 右边框分隔） */}
      <div style={{
        width: 196, flexShrink: 0, background: '#fafafa',
        borderRight: '1px solid #f0f0f0', padding: '8px 0', overflowY: 'auto',
      }}>
        <div style={{ padding: '8px 14px 6px', fontSize: 13, color: '#999', fontWeight: 500 }}>选择对话对象</div>
        {CHAT_TARGETS.map((t) => {
          const active = t.key === activeTarget
          return (
            <div
              key={t.key}
              onClick={() => switchTarget(t.key)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '9px 14px', cursor: 'pointer',
                background: active ? '#e6f4ff' : 'transparent',
                borderLeft: active ? '3px solid #1677ff' : '3px solid transparent',
                transition: 'background .2s',
              }}
            >
              <Avatar size={36} icon={t.icon} style={{ background: t.bg, flexShrink: 0 }} />
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: active ? 600 : 500, color: active ? '#1677ff' : '#333', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {t.name}
                </div>
                <div style={{ fontSize: 11, color: '#999', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {t.desc}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* 右侧聊天区 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: '#fff' }}>
      <div style={{ padding: '10px 16px', borderBottom: '1px solid #f0f0f0', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <Avatar size={26} icon={currentTarget.icon} style={{ background: currentTarget.bg, flexShrink: 0 }} />
        <Text strong style={{ fontSize: 18 }}>{currentTarget.name}</Text>
        {/* #F3 新建会话 / 历史会话 仅智能客服保留，商家 A/B/C 不显示 */}
        {activeTarget === 'ai' && (
          <>
            <Tag color="blue">当前会话 {currentSid}</Tag>
            <Select
              size="small"
              style={{ minWidth: 220 }}
              placeholder="切换历史会话"
              value={sessions.some((s) => s.session_id === currentSid) ? currentSid : undefined}
              onChange={switchSession}
              options={sessions.map((s) => ({
                value: s.session_id,
                label: `${s.session_id}（${s.message_count}条）${s.last_message ? ' · ' + s.last_message.slice(0, 12) : ''}`,
              }))}
              notFoundContent="暂无历史会话"
            />
            <Button size="small" icon={<PlusOutlined />} onClick={createNewSession}>新建会话</Button>
          </>
        )}
      </div>

      {/* 消息区（#F1：快捷用语固定在聊天框内部底部，不随消息滚动） */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#fafafa', overflow: 'hidden' }}>
        {/* 消息滚动区 */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
          {messages.length === 0 && (
            <Text type="secondary">{currentTarget.welcome}</Text>
          )}
          {messages.map((m, i) => (
            <div key={i}>
              <MessageBubble
                role={m.role}
                content={m.content}
                showCursor={streaming && m.role === 'assistant' && i === messages.length - 1}
                ts={m.ts}
                aiAvatarIcon={currentTarget.icon}
                aiAvatarBg={currentTarget.bg}
              />
              {/* 满意度评价（仅 assistant 且有 chat_id）；paddingLeft 对齐 AI 气泡（头像 34 + 间距 8） */}
              {m.role === 'assistant' && m.chat_id && !streaming && (
                <div style={{ fontSize: 12, marginBottom: 8, paddingLeft: 46 }}>
                  {rated[m.chat_id] ? (
                    <Text type="secondary">已评价：{rated[m.chat_id] === 1 ? '👍 满意' : '👎 不满意'}</Text>
                  ) : (
                    <Space size={4}>
                      <Button size="small" type="text" icon={<LikeOutlined />} onClick={() => handleRate(m.chat_id!, 1)}>满意</Button>
                      <Button size="small" type="text" icon={<DislikeOutlined />} onClick={() => setDislikeTarget(m.chat_id!)}>不满意</Button>
                    </Space>
                  )}
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* 快捷用语（#F8：智能客服 FAQ 动态；商家各自定制；#F1 置于聊天框底层，背景与聊天区一致） */}
        <div style={{ padding: '4px 12px 10px', background: '#fafafa' }}>
          <Space wrap size={[6, 6]}>
            {quickQuestionsToShow.map((q) => (
              <Button key={q} size="small" disabled={streaming} onClick={() => send(q)}>{q}</Button>
            ))}
          </Space>
        </div>
      </div>

      {/* 输入区（含停止按钮 #1）；工具栏：图片/表情/服务评价（#E2） */}
      <div style={{ marginTop: 12 }}>
        <Space size={4} style={{ marginBottom: 4 }}>
          <Upload
            accept="image/*"
            showUploadList={false}
            beforeUpload={handleSendImage}
            disabled={streaming}
          >
            <Button size="small" icon={<PictureOutlined />} disabled={streaming}>图片</Button>
          </Upload>
          <Popover
            trigger="click"
            placement="topLeft"
            content={
              <div style={{ width: 264, display: 'flex', flexWrap: 'wrap', gap: 2 }}>
                {EMOJIS.map((e) => (
                  <Button
                    key={e}
                    type="text"
                    size="small"
                    style={{ fontSize: 18, width: 36, height: 36, padding: 0 }}
                    onClick={() => insertEmoji(e)}
                  >
                    {e}
                  </Button>
                ))}
              </div>
            }
          >
            <Button size="small" icon={<SmileOutlined />} disabled={streaming}>表情</Button>
          </Popover>
          <Button size="small" icon={<StarOutlined />} onClick={openServiceRate}>评价本次服务</Button>
        </Space>
        <div style={{ display: 'flex', gap: 8 }}>
          <Input
            value={input}
            placeholder="请输入您的问题，例如：X30多少钱 / 查我的订单 / 转人工"
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={() => send(input)}
            disabled={streaming}
          />
          {streaming ? (
            <Button danger onClick={stop}>⏹ 停止</Button>
          ) : (
            <Button type="primary" onClick={() => send(input)}>发送</Button>
          )}
        </div>
      </div>
      </div>

      {/* 差评原因弹窗（第二波 #5） */}
      <Modal
        title="👎 请问哪里让您不满意？"
        open={dislikeTarget !== null}
        onOk={submitDislike}
        onCancel={() => setDislikeTarget(null)}
        okText="提交反馈"
        cancelText="取消"
      >
        <Radio.Group
          value={dislikeReason}
          onChange={(e) => setDislikeReason(e.target.value)}
          style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}
        >
          {DISLIKE_REASONS.map((r) => (
            <Radio key={r} value={r}>{r}</Radio>
          ))}
        </Radio.Group>
        {/* 选中"其他"时展开自定义输入（问题 D） */}
        {dislikeReason === '其他' && (
          <Input
            style={{ marginTop: 12 }}
            placeholder="请简单描述您不满意的地方（选填）"
            value={dislikeOther}
            onChange={(e) => setDislikeOther(e.target.value)}
            maxLength={100}
          />
        )}
      </Modal>

      {/* 本次服务评价弹窗（#E3 星级）：1-5 星 + 是否解决 + 问题描述（1-3 星显示） */}
      <Modal
        title="⭐ 请对本次服务进行评价"
        open={rateModalOpen}
        onOk={submitServiceRate}
        onCancel={() => setRateModalOpen(false)}
        okText="提交评价"
        cancelText="取消"
        destroyOnClose
      >
        {/* 星级选择 */}
        <div style={{ textAlign: 'center', margin: '20px 0 8px' }}>
          <Rate
            value={rateStars}
            onChange={(v) => {
              setRateStars(v)
              setRateSolved(null)
              setRateDesc('')
            }}
            style={{ fontSize: 34 }}
          />
          <div style={{ marginTop: 8, fontSize: 14, color: rateStars ? '#1677ff' : '#999' }}>
            {rateStars ? STAR_TIPS[rateStars] : '点击星星评分'}
          </div>
        </div>

        {rateStars > 0 && (
          <div style={{ marginTop: 16 }}>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>问题是否解决？</div>
            <Radio.Group
              value={rateSolved}
              onChange={(e) => setRateSolved(e.target.value)}
              style={{ display: 'flex', gap: 16 }}
            >
              <Radio value="已解决">✅ 已解决</Radio>
              <Radio value="未解决">❌ 未解决</Radio>
            </Radio.Group>

            {/* 1-3 星：显示问题描述输入框（4-5 星不显示） */}
            {rateStars <= 3 && (
              <Input.TextArea
                style={{ marginTop: 12 }}
                placeholder="请描述问题..."
                value={rateDesc}
                onChange={(e) => setRateDesc(e.target.value)}
                maxLength={200}
                rows={3}
                showCount
              />
            )}
          </div>
        )}
      </Modal>
      </div>
    </div>
  )
}
