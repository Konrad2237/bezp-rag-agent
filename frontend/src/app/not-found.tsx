import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
      <div className="text-center">
        <h2 className="text-white text-xl font-bold mb-4">Strona nie istnieje</h2>
        <Link href="/" className="text-zinc-400 hover:text-white text-sm">
          Wróć do logowania
        </Link>
      </div>
    </div>
  )
}
