import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

document.addEventListener('pointermove', (e) => {
  const alvo = (e.target as HTMLElement).closest?.('.cartao, .metrica') as HTMLElement | null
  if (!alvo) return
  const r = alvo.getBoundingClientRect()
  alvo.style.setProperty('--mx', `${((e.clientX - r.left) / r.width) * 100}%`)
  alvo.style.setProperty('--my', `${((e.clientY - r.top) / r.height) * 100}%`)
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
