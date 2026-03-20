import { useState } from 'react'
import { Send, CheckCircle } from 'lucide-react'

export default function QuoteForm({ compact = false }) {
  const [submitted, setSubmitted] = useState(false)
  const [form, setForm] = useState({ nome: '', telefone: '', tipo: '', email: '', mensagem: '' })

  const handleSubmit = (e) => {
    e.preventDefault()
    setSubmitted(true)
    setTimeout(() => setSubmitted(false), 4000)
    setForm({ nome: '', telefone: '', tipo: '', email: '', mensagem: '' })
  }

  const update = (field) => (e) => setForm(prev => ({ ...prev, [field]: e.target.value }))

  const inputClass = 'w-full px-4 py-3 bg-slate-800/50 border border-slate-700/50 rounded-lg text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-emerald-400/50 focus:ring-1 focus:ring-emerald-400/20 transition-all'

  if (submitted) {
    return (
      <div className="text-center py-8">
        <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
        <p className="text-slate-50 font-semibold text-lg">Recebemos sua solicitação!</p>
        <p className="text-slate-400 text-sm mt-1">Entraremos em contato em breve.</p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className={compact ? 'space-y-4' : 'grid grid-cols-1 sm:grid-cols-2 gap-4'}>
        <input
          type="text"
          placeholder="Seu nome"
          required
          value={form.nome}
          onChange={update('nome')}
          className={inputClass}
        />
        <input
          type="tel"
          placeholder="Telefone / WhatsApp"
          required
          value={form.telefone}
          onChange={update('telefone')}
          className={inputClass}
        />
        {!compact && (
          <input
            type="email"
            placeholder="Seu e-mail"
            value={form.email}
            onChange={update('email')}
            className={inputClass}
          />
        )}
        <select
          required
          value={form.tipo}
          onChange={update('tipo')}
          className={inputClass}
        >
          <option value="">Tipo de plano</option>
          <option value="individual">Individual</option>
          <option value="familiar">Familiar</option>
          <option value="empresarial">Empresarial</option>
          <option value="pme">PME</option>
        </select>
      </div>
      {!compact && (
        <textarea
          placeholder="Mensagem (opcional)"
          rows={3}
          value={form.mensagem}
          onChange={update('mensagem')}
          className={inputClass + ' resize-none'}
        />
      )}
      <button
        type="submit"
        className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-emerald-500 hover:bg-emerald-400 text-slate-900 font-semibold rounded-lg transition-all duration-200 hover:shadow-lg hover:shadow-emerald-500/20"
      >
        <Send className="w-4 h-4" />
        Solicitar Cotação Grátis
      </button>
    </form>
  )
}
