import { MessageCircle } from 'lucide-react'

export default function WhatsAppButton() {
  const phoneNumber = '5500000000000'
  const message = encodeURIComponent('Ola! Gostaria de uma cotacao de plano de saude.')

  return (
    <a
      href={`https://wa.me/${phoneNumber}?text=${message}`}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 50,
        width: '56px',
        height: '56px',
        borderRadius: '50%',
        background: '#25d366',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: '0 4px 16px rgba(37,211,102,0.4)',
        transition: 'transform 0.2s',
        textDecoration: 'none',
      }}
      aria-label="Falar no WhatsApp"
    >
      <MessageCircle style={{ width: '26px', height: '26px', color: '#fff' }} />
    </a>
  )
}
