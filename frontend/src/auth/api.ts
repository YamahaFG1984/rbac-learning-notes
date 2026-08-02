import { client } from '@/api/client'
import type { Profile } from '@/types/auth'

/** 种下 csrftoken cookie。⚠️ 必须在登录**之前**调——登录本身也是 POST。 */
export async function ensureCsrfCookie() {
  await client.get('/auth/csrf/')
}

export async function loginRequest(username: string, password: string) {
  await ensureCsrfCookie()
  const { data } = await client.post<Profile>('/auth/login/', { username, password })
  return data
}

export async function logoutRequest() {
  await client.post('/auth/logout/')
}

export async function fetchProfile() {
  const { data } = await client.get<Profile>('/auth/profile/')
  return data
}
