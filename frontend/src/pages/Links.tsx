import { useState, type FormEvent } from 'react'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, ApiError, type CreateLink, type LinkList, type ManagedLink } from '../api'
import { signIn, signOut } from '../auth'
import { useAuth } from '../AuthContext'
import { Badge, BrailleSpinner, Button, Input, Panel, StatusLine } from '../components/Ui'

// eslint-disable-next-line react-refresh/only-export-components
export function isHttpUrl(value: string) {
  try { return ['http:', 'https:'].includes(new URL(value).protocol) }
  catch { return false }
}

function LinkRow({ link }: { link: ManagedLink }) {
  const [copied, setCopied] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(link.shortened_url)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch { setCopied(false) }
  }
  return <article className={`link-row ${link.status !== 'active' ? 'link-inactive' : ''}`}>
    <div className="link-primary"><Link to={`/links/${encodeURIComponent(link.short_code)}`} className="short-url">{link.shortened_url}</Link><Button kind="ghost" onClick={copy} aria-label={`Copy ${link.shortened_url}`}>{copied ? 'copied' : 'copy'}</Button></div>
    <p className="destination" title={link.original_url}>{link.original_url}</p>
    <div className="link-meta"><time dateTime={link.created_at}>{new Date(link.created_at).toLocaleDateString()}</time><Badge status={link.status} /></div>
  </article>
}

export function Links() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [url, setUrl] = useState('')
  const [alias, setAlias] = useState('')
  const [title, setTitle] = useState('')
  const [days, setDays] = useState(7)
  const [maxVisits, setMaxVisits] = useState('')
  const [policyType, setPolicyType] = useState<CreateLink['policy']['type']>('public')
  const [password, setPassword] = useState('')
  const [ipList, setIpList] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const list = useInfiniteQuery({
    queryKey: ['links', user?.profile.sub],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => api<LinkList>(user!, `/links?limit=100&offset=${pageParam}`),
    getNextPageParam: (last, pages) => pages.length * 100 < last.total ? pages.length * 100 : undefined,
    enabled: !!user,
  })
  const create = useMutation({
    mutationFn: (body: CreateLink) => api<{ shortened_url: string }>(user!, '/link/', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: result => { setUrl(''); setAlias(''); setTitle(''); setMaxVisits(''); setPassword(''); setIpList(''); setSuccess(`Created ${result.shortened_url}`); void queryClient.invalidateQueries({ queryKey: ['links'] }) },
  })
  const links = list.data?.pages.flatMap(page => page.items) || []
  const total = list.data?.pages[0]?.total || 0
  function submit(event: FormEvent) {
    event.preventDefault()
    setFormError(null); setSuccess(null)
    if (!isHttpUrl(url)) { setFormError('Enter an http:// or https:// URL'); return }
    if (alias && !/^[A-Za-z0-9_-]{3,32}$/.test(alias)) { setFormError('Alias must be 3–32 letters, numbers, underscores, or hyphens'); return }
    if (!Number.isInteger(days) || days < 1 || days > 30) { setFormError('Expiry must be 1–30 days'); return }
    if (title.trim().length > 256) { setFormError('Title must be at most 256 characters'); return }
    const visitLimit = Number(maxVisits)
    if (maxVisits && (!Number.isSafeInteger(visitLimit) || visitLimit < 1)) { setFormError('Visit limit must be a positive whole number'); return }
    if (policyType === 'password_protected' && (!password || password.length > 256)) { setFormError('Password must be 1–256 characters'); return }
    const allowedIps = ipList.split(/[\n,]+/).map(value => value.trim()).filter(Boolean)
    if (policyType === 'ip_restricted' && allowedIps.length === 0) { setFormError('Enter at least one allowed IP address or CIDR range'); return }
    const policy: CreateLink['policy'] = policyType === 'password_protected'
      ? { type: policyType, password }
      : policyType === 'ip_restricted'
        ? { type: policyType, ip_list: allowedIps }
        : { type: 'public' }
    create.mutate({ url, ttl_seconds: days * 86400, policy, ...(alias ? { short_code: alias } : {}), ...(title.trim() ? { title: title.trim() } : {}), ...(maxVisits ? { max_visits: visitLimit } : {}) })
  }
  const error = formError || (create.error instanceof Error ? create.error.message : null)
  return <main className="content-page">
    <header className="page-header"><div className="header-heading"><span className="brand-mark">zipp<span className="cursor">_</span></span><h1>links</h1></div><Button kind="ghost" onClick={() => void signOut()}>sign out</Button></header>
    <Panel><form onSubmit={submit} className="create-form">
      <Input id="long-url" label="long url" type="url" placeholder="https://" value={url} onChange={event => setUrl(event.target.value)} required />
      <Button type="submit" disabled={create.isPending}>{create.isPending ? <BrailleSpinner /> : 'shorten >'}</Button>
      <details className="advanced-fields"><summary>options</summary>
        <Input id="title" label="title (optional)" value={title} onChange={event => setTitle(event.target.value)} maxLength={256} />
        <Input id="alias" label="alias (optional)" value={alias} onChange={event => setAlias(event.target.value)} minLength={3} maxLength={32} />
        <Input id="expiry" label="expires after (days)" type="number" min={1} max={30} value={days} onChange={event => setDays(Number(event.target.value))} />
        <Input id="max-visits" label="maximum visits (optional)" type="number" min={1} step={1} value={maxVisits} onChange={event => setMaxVisits(event.target.value)} />
        <label className="field" htmlFor="policy-type"><span>access</span><select id="policy-type" value={policyType} onChange={event => setPolicyType(event.target.value as CreateLink['policy']['type'])}><option value="public">public</option><option value="password_protected">password protected</option><option value="ip_restricted">IP restricted</option></select></label>
        {policyType === 'password_protected' && <Input id="link-password" label="link password" type="password" value={password} onChange={event => setPassword(event.target.value)} minLength={1} maxLength={256} required autoComplete="new-password" />}
        {policyType === 'ip_restricted' && <label className="field" htmlFor="allowed-ips"><span>allowed IP addresses or CIDR ranges</span><textarea id="allowed-ips" value={ipList} onChange={event => setIpList(event.target.value)} placeholder={'203.0.113.4\n198.51.100.0/24'} rows={4} required /><small>Separate entries with commas or new lines. Visitors outside these ranges cannot open the link.</small></label>}
      </details>
      <StatusLine error={error} success={success} />
    </form></Panel>
    <div className="section-heading">your links ({total})</div>
    {list.isPending && <Panel><BrailleSpinner /> loading links</Panel>}
    {list.error && <Panel><StatusLine error={list.error instanceof ApiError && list.error.status === 401 ? 'Session expired. Sign in again.' : list.error.message} />{list.error instanceof ApiError && list.error.status === 401 && <Button onClick={() => void signIn('/links')}>sign in</Button>}<Button kind="ghost" onClick={() => void list.refetch()}>retry</Button></Panel>}
    {!list.isPending && !list.error && links.length === 0 && <Panel><p>No links yet. Create your first one above.</p></Panel>}
    {links.length > 0 && <div className="link-list">{links.map(link => <LinkRow key={link.id} link={link} />)}</div>}
    {list.hasNextPage && <Button kind="ghost" onClick={() => void list.fetchNextPage()} disabled={list.isFetchingNextPage}>{list.isFetchingNextPage ? <BrailleSpinner /> : 'load more'}</Button>}
  </main>
}
