import { UserManager, WebStorageStateStore } from 'oidc-client-ts'
import { config } from './config'

export const userManager = new UserManager({
  authority: config.issuer,
  client_id: config.clientId,
  redirect_uri: config.redirectUri,
  response_type: 'code',
  scope: 'openid email',
  userStore: new WebStorageStateStore({ store: window.sessionStorage }),
  stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
  automaticSilentRenew: true,
  monitorSession: false,
})

export async function signIn(returnTo = '/links') {
  await userManager.signinRedirect({ state: { returnTo } })
}

export async function signOut() {
  await userManager.removeUser()
  const url = new URL(`${config.domain}/logout`)
  url.searchParams.set('client_id', config.clientId)
  url.searchParams.set('logout_uri', config.logoutUri)
  window.location.assign(url.toString())
}
