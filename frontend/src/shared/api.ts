export const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const token = window.sessionStorage.getItem('webapp_api_token');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`${apiBaseUrl}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = `Erreur API (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((issue: {loc?: string[]; msg?: string}) => `${issue.loc?.slice(1).join('.') || 'Formulaire'} : ${issue.msg || 'Valeur invalide'}`).join(' · ');
    } catch { /* Preserve the HTTP status when the response is not JSON. */ }
    if (response.status === 401) window.dispatchEvent(new Event('session-expired'));
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Erreur de connexion';
}
