// 前后端共享的类型定义

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  chat_id?: string
  /** HH:mm 时间戳（第一波 #7；仅新消息有，历史消息无此字段） */
  ts?: string
}

export interface ChatResponse {
  session_id: string
  reply: string
  intent: string
  action: string
  chat_id: string
  ticket_id?: string | null
  tool_calls: string[]
  elapsed_ms: number
}

export interface IntentResponse {
  intent: string
  confidence: number
  matched: string[]
}

export interface Ticket {
  ticket_id: string
  session_id: string | null
  user_id: string | null
  reason: string
  status: string
  transcript: ChatMessage[]
  created_at: string
}

export interface Stats {
  total: number
  intent_dist: Record<string, number>
  action_dist: Record<string, number>
  escalate_rate: number
  faq_hit_rate: number
  tool_calls: number
  /** #E4 星级评价统计 */
  rated_count: number
  bad_count: number
  bad_rate: number
  star_dist: Record<string, number>
  solved_dist: Record<string, number>
}

/** #E4 1-3 星差评记录（运营端坐席台展示） */
export interface BadRating {
  chat_id: string
  ts: string
  session_id: string | null
  user_id: string | null
  query: string
  intent: string
  rating: number
  solved: string | null
  reason: string | null
  reply: string | null
  /** #E5 坐席回复 */
  rating_reply: string | null
  rating_replied_at: string | null
}

export interface ChatLogEntry {
  ts?: string
  query?: string
  intent?: string
  reply?: string
  ticket_id?: string
  session_id?: string
}

export interface SessionItem {
  session_id: string
  message_count: number
  last_message: string
  updated_at: string
}

export interface Badcase {
  escalations: ChatLogEntry[]
  faq_misses: ChatLogEntry[]
  empty_replies: ChatLogEntry[]
}

export interface FaqItem {
  id: number
  question: string
  answer: string
  keywords: string
  category: string
}
