'use client'

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html lang="pl">
      <body style={{ background: '#09090b', color: '#ededed', fontFamily: 'sans-serif', display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', margin: 0 }}>
        <div style={{ textAlign: 'center' }}>
          <h2 style={{ marginBottom: '16px' }}>Coś poszło nie tak.</h2>
          <button onClick={() => reset()} style={{ background: 'white', color: 'black', border: 'none', padding: '10px 20px', borderRadius: '6px', cursor: 'pointer' }}>
            Spróbuj ponownie
          </button>
        </div>
      </body>
    </html>
  )
}
