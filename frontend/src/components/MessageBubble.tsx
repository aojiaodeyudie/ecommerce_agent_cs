// 消息气泡组件：头像 + Markdown 渲染 + 打字光标 + 时间戳（第一波 #2/#4/#7，头像 #E1）
// #F2：AI 头像可自定义（多对话对象：智能客服 / 商家 A/B/C）
// 样式见 src/styles/markdown.css（main.tsx 统一引入，避免每个气泡重复注入 <style>）
import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Avatar } from 'antd'
import { RobotOutlined, UserOutlined } from '@ant-design/icons'

interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: string
  /** 流式生成中且为最后一条消息时，末尾显示闪烁光标 */
  showCursor?: boolean
  /** HH:mm 时间戳（仅新消息有，历史消息无此字段） */
  ts?: string
  /** #F2 AI 头像自定义：图标与背景色（不传用默认机器人头像） */
  aiAvatarIcon?: React.ReactNode
  aiAvatarBg?: string
}

// 头像尺寸
const AVATAR_SIZE = 34

export default function MessageBubble({
  role, content, showCursor, ts, aiAvatarIcon, aiAvatarBg,
}: MessageBubbleProps) {
  const isUser = role === 'user'
  // 用户消息若含 Markdown 图片语法（![...](url)），走 Markdown 渲染以展示图片
  const hasImageMarkdown = /!\[[^\]]*\]\([^)]+\)/.test(content)
  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      alignItems: 'flex-start',
      gap: 8,
      marginBottom: 12,
    }}>
      {/* AI 头像在左（客服）；#F2 支持按对话对象自定义 */}
      {!isUser && (
        <Avatar
          size={AVATAR_SIZE}
          icon={aiAvatarIcon ?? <RobotOutlined />}
          style={{
            flexShrink: 0,
            background: aiAvatarBg ?? 'linear-gradient(135deg, #4f8cff, #7a5cff)',
            boxShadow: '0 2px 6px rgba(79,140,255,.35)',
          }}
        />
      )}

      <div style={{
        maxWidth: '78%',
        padding: '8px 12px',
        borderRadius: 10,
        background: isUser ? '#1677ff' : '#ffffff',
        color: isUser ? '#fff' : '#000',
        boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
        wordBreak: 'break-word',
        overflow: 'hidden',
      }}>
        {isUser ? (
          hasImageMarkdown ? (
            // 含图片的用户消息：Markdown 渲染
            <div className="markdown-body" style={{ color: '#fff' }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>
          ) : (
            // 普通用户消息：纯文本，保留换行
            <div style={{ whiteSpace: 'pre-wrap' }}>{content}</div>
          )
        ) : (
          // 客服消息：Markdown 渲染 + 流式光标
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || ''}</ReactMarkdown>
            {showCursor && <span className="typing-cursor" />}
          </div>
        )}
        {ts && (
          <div style={{
            fontSize: 11,
            color: isUser ? 'rgba(255,255,255,0.75)' : '#999',
            marginTop: 4,
            textAlign: 'right',
          }}>
            {ts}
          </div>
        )}
      </div>

      {/* 用户头像在右 */}
      {isUser && (
        <Avatar
          size={AVATAR_SIZE}
          icon={<UserOutlined />}
          style={{
            flexShrink: 0,
            background: '#e8f1ff',
            color: '#1677ff',
            border: '1px solid #bcd7ff',
          }}
        />
      )}
    </div>
  )
}
