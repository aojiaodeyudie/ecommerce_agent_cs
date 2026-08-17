// API 客户端：封装 fetch + SSE 流式解析
import type {
  BadRating, Badcase, ChatMessage, ChatResponse, FaqItem, IntentResponse, SessionItem, Stats, Ticket,
} from './types'

const BASE = '/api'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* 忽略解析失败 */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

function tryParse(s: string): unknown {
  try { return JSON.parse(s) } catch { return s }
}

// ---------------------------------------------------------------- chat

export function chat(message: string, sessionId?: string, userId = '1001', shopId?: string) {
  return request<ChatResponse>(`${BASE}/chat`, {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId, user_id: userId, shop_id: shopId }),
  })
}

export interface StreamEvent {
  event: string          // intent | token | done | error
  data: any
}

// SSE 流式对话（POST + ReadableStream 解析；signal 支持停止生成 #1）
export async function* chatStream(
  message: string,
  sessionId?: string,
  userId = '1001',
  signal?: AbortSignal,
  shopId?: string,
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, user_id: userId, shop_id: shopId }),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    // 统一 CRLF → LF（sse-starlette 输出 \r\n\r\n 块分隔，必须归一化否则切块失败）
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const lines = block.split('\n')
      let event = 'message'
      let data = ''
      for (const line of lines) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) {
          // 多行 data: 按 SSE 规范用换行连接（保留 markdown 换行，不用 trim 吞掉空白）
          const payload = line.slice(5)
          if (data === '') data = payload
          else data += '\n' + payload
        }
      }
      if (data.trim() !== '') yield { event, data: tryParse(data) }
    }
  }
}

export function intent(text: string) {
  return request<IntentResponse>(`${BASE}/intent`, { method: 'POST', body: JSON.stringify({ text }) })
}

// ---------------------------------------------------------------- 会话

export function getHistory(sessionId: string) {
  return request<{ session_id: string; messages: ChatMessage[] }>(`${BASE}/chat/history/${sessionId}`)
}

export interface SessionList {
  items: SessionItem[]
  total: number
}

export function getSessions(userId: string) {
  return request<SessionList>(`${BASE}/chat/sessions?user_id=${encodeURIComponent(userId)}`)
}

export function rate(chatId: string, rating: number, solved?: string, reason?: string) {
  const params = new URLSearchParams({ chat_id: chatId, rating: String(rating) })
  if (solved) params.set('solved', solved)
  if (reason) params.set('reason', reason)
  return request<{ ok: boolean }>(`${BASE}/chat/rating?${params.toString()}`, { method: 'POST' })
}

// 上传图片：返回 { url }（以 /uploads/ 开头的可访问路径）
export async function uploadImage(file: File): Promise<{ url: string }> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`${BASE}/chat/upload`, { method: 'POST', body: fd })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (body.detail) detail = body.detail
    } catch { /* 忽略 */ }
    throw new Error(detail)
  }
  return res.json() as Promise<{ url: string }>
}

// ---------------------------------------------------------------- ops

export interface TicketPage {
  items: Ticket[]
  total: number
  page: number
  size: number
}

export function getTickets(params?: {
  page?: number
  size?: number
  keyword?: string
  status?: string
}) {
  const q = new URLSearchParams()
  if (params?.page) q.set('page', String(params.page))
  if (params?.size) q.set('size', String(params.size))
  if (params?.keyword) q.set('keyword', params.keyword)
  if (params?.status) q.set('status', params.status)
  const qs = q.toString()
  return request<TicketPage>(`${BASE}/tickets${qs ? `?${qs}` : ''}`)
}

export function resolveTicket(id: string) { return request<{ ok: boolean }>(`${BASE}/tickets/${id}/resolve`, { method: 'POST' }) }
export function replyTicket(id: string, reply: string) {
  return request<{ ok: boolean }>(`${BASE}/tickets/${id}/reply?reply=${encodeURIComponent(reply)}`, { method: 'POST' })
}
export function deleteTicket(id: string) { return request<{ ok: boolean }>(`${BASE}/tickets/${id}`, { method: 'DELETE' }) }
export function deleteAllOpenTickets() {
  return request<{ ok: boolean; deleted_count: number }>(`${BASE}/tickets`, { method: 'DELETE' })
}
export function getStats(fromDate?: string, toDate?: string) {
  const q = new URLSearchParams()
  if (fromDate) q.set('from', fromDate)
  if (toDate) q.set('to', toDate)
  const qs = q.toString()
  return request<Stats>(`${BASE}/stats${qs ? `?${qs}` : ''}`)
}
export function getBadcase() { return request<Badcase>(`${BASE}/badcase`) }
export function getBadRatings(limit = 50) {
  return request<BadRating[]>(`${BASE}/ratings/bad?limit=${limit}`)
}
// #E5：差评删除 / 一键删除 / 回复
export function deleteBadRating(chatId: string) {
  return request<{ ok: boolean }>(`${BASE}/ratings/bad/${chatId}`, { method: 'DELETE' })
}
export function deleteAllBadRatings() {
  return request<{ ok: boolean; deleted_count: number }>(`${BASE}/ratings/bad`, { method: 'DELETE' })
}
export function replyBadRating(chatId: string, reply: string) {
  return request<{ ok: boolean }>(
    `${BASE}/ratings/bad/${chatId}/reply?reply=${encodeURIComponent(reply)}`,
    { method: 'POST' },
  )
}
export function getFaqs() { return request<FaqItem[]>(`${BASE}/faq`) }
export function addFaq(item: { question: string; answer: string; keywords?: string; category?: string }) {
  return request<FaqItem>(`${BASE}/faq`, { method: 'POST', body: JSON.stringify(item) })
}
export function deleteFaq(id: number) { return request<{ ok: boolean }>(`${BASE}/faq/${id}`, { method: 'DELETE' }) }
