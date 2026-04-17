const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function getTokenExpiry(token: string): number {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.exp ?? 0
  } catch {
    return 0
  }
}

/**
 * Zwraca ważny token JWT.
 * Jeśli token wygasa w ciągu 5 minut — cicho odświeża go przez /auth/refresh.
 * Jeśli refresh się nie uda — zwraca null (user musi się zalogować ponownie).
 */
export async function getValidToken(): Promise<string | null> {
  const token = localStorage.getItem('bezp_token')
  if (!token) return null

  const exp = getTokenExpiry(token)
  const now = Math.floor(Date.now() / 1000)

  if (exp - now > 300) return token

  // Token wygasa za mniej niż 5 minut — odśwież
  const refreshToken = localStorage.getItem('bezp_refresh_token')
  if (!refreshToken) {
    localStorage.removeItem('bezp_token')
    return null
  }

  try {
    const res = await fetch(`${API_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) {
      localStorage.removeItem('bezp_token')
      localStorage.removeItem('bezp_refresh_token')
      return null
    }
    const data = await res.json()
    localStorage.setItem('bezp_token', data.access_token)
    localStorage.setItem('bezp_refresh_token', data.refresh_token)
    return data.access_token
  } catch {
    return null
  }
}
