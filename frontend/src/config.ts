const required = (name: string) => {
  const value = import.meta.env[name]
  if (!value) throw new Error(`Missing ${name}. Copy .env.example to .env.local and configure it.`)
  return String(value)
}

export const config = {
  apiBaseUrl: required('VITE_API_BASE_URL').replace(/\/$/, ''),
  issuer: required('VITE_COGNITO_ISSUER').replace(/\/$/, ''),
  clientId: required('VITE_COGNITO_CLIENT_ID'),
  domain: required('VITE_COGNITO_DOMAIN').replace(/\/$/, ''),
  redirectUri: required('VITE_COGNITO_REDIRECT_URI'),
  logoutUri: required('VITE_COGNITO_LOGOUT_URI'),
}
