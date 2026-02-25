import { useState } from 'react'
import './App.css'

interface Document {
  id: string
  name: string
  size: number
  uploaded_at: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
}

function App() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [theme, setTheme] = useState<'light' | 'dark'>('dark')

  const handleUpload = async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    
    const res = await fetch('http://localhost:8000/documents', {
      method: 'POST',
      body: formData,
    })
    const data = await res.json()
    setDocuments([...documents, data.document])
  }

  const handleSend = async () => {
    if (!input.trim() || !selectedDoc) return
    
    const userMsg: Message = { role: 'user', content: input }
    setMessages([...messages, userMsg])
    setInput('')
    
    const res = await fetch('http://localhost:8000/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        doc_id: selectedDoc.id,
        question: input,
        api_key: apiKey,
      }),
    })
    const data = await res.json()
    
    const assistantMsg: Message = { 
      role: 'assistant', 
      content: data.answer,
      sources: data.sources,
    }
    setMessages([...messages, userMsg, assistantMsg])
  }

  return (
    <div className={`app ${theme}`}>
      <div className="sidebar">
        <h2>📄 ChatDoc Pro</h2>
        
        <div className="api-key-section">
          <input
            type="password"
            placeholder="API Key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </div>
        
        <div className="upload-section">
          <input
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
          />
        </div>
        
        <div className="doc-list">
          <h3>文档列表</h3>
          {documents.map((doc) => (
            <div
              key={doc.id}
              className={`doc-item ${selectedDoc?.id === doc.id ? 'active' : ''}`}
              onClick={() => setSelectedDoc(doc)}
            >
              📄 {doc.name}
            </div>
          ))}
        </div>
        
        <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
          {theme === 'dark' ? '🌞 浅色' : '🌙 深色'}
        </button>
      </div>
      
      <div className="main">
        {selectedDoc ? (
          <>
            <div className="chat">
              {messages.length === 0 && (
                <div className="welcome">
                  <h3>欢迎使用 ChatDoc Pro</h3>
                  <p>基于文档 "{selectedDoc.name}" 的智能问答助手</p>
                </div>
              )}
              {messages.map((msg, i) => (
                <div key={i} className={`message ${msg.role}`}>
                  <div className="content">{msg.content}</div>
                  {msg.sources && (
                    <div className="sources">
                      来源: {msg.sources.join(', ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="input-area">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                placeholder="请输入您的问题..."
              />
              <button onClick={handleSend}>发送</button>
            </div>
          </>
        ) : (
          <div className="no-doc">
            <h3>请选择或上传一个文档开始问答</h3>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
