const DEFAULT_API_PORT = '8000';

function trimTrailingSlash(value: string) {
  return value.replace(/\/$/, '');
}

function resolveApiBaseUrl() {
  const configured = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  if (configured) return trimTrailingSlash(configured);

  if (import.meta.env.DEV) {
    return '';
  }

  if (typeof window !== 'undefined' && window.location.hostname) {
    const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
    return `${protocol}//${window.location.hostname}:${DEFAULT_API_PORT}`;
  }

  return `http://127.0.0.1:${DEFAULT_API_PORT}`;
}

export const API_BASE_URL = resolveApiBaseUrl();
