import { forwardRef, useEffect, useRef, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from 'react'

export function DotGridBackground({ children }: { children: ReactNode }) {
  return <div className="app-shell">{children}</div>
}

export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>{children}</section>
}

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { kind?: 'primary' | 'ghost' | 'danger' }>(function Button({ kind = 'primary', children, ...props }, ref) {
  return <button ref={ref} className={`button button-${kind}`} {...props}>{children}</button>
})

export function Input({ label, id, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; id: string }) {
  return <label className="field" htmlFor={id}><span>{label}</span><input id={id} {...props} /></label>
}

export function Badge({ status }: { status: string }) {
  return <span className={`badge badge-${status}`}>{status}</span>
}

const frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
export function BrailleSpinner() {
  const [frame, setFrame] = useState(0)
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const timer = window.setInterval(() => setFrame(value => (value + 1) % frames.length), 90)
    return () => window.clearInterval(timer)
  }, [])
  return <span role="status" aria-label="Loading">{frames[frame]}</span>
}

export function StepProgress({ step }: { step: number }) {
  return <div className="step-progress" role="progressbar" aria-valuenow={step} aria-valuemin={0} aria-valuemax={4} aria-label="Sign-in progress">{[0, 1, 2, 3].map(index => <span className={index < step ? 'filled' : ''} key={index} />)}</div>
}

export function StatusLine({ error, success }: { error?: string | null; success?: string | null }) {
  if (!error && !success) return null
  return <p className={`status-line ${error ? 'status-error' : 'status-success'}`} role={error ? 'alert' : 'status'}>{error || success}</p>
}

export function ConfirmPanel({ title, body, onCancel, onConfirm, pending }: { title: string; body: string; onCancel: () => void; onConfirm: () => void; pending: boolean }) {
  const cancelRef = useRef<HTMLButtonElement>(null)
  useEffect(() => { cancelRef.current?.focus() }, [])
  return <section className="confirm-panel" role="group" aria-label={title} onKeyDown={event => { if (event.key === 'Escape') onCancel() }}>
    <h2>{title}</h2><p>{body}</p>
    <div className="confirm-actions"><Button ref={cancelRef} kind="ghost" onClick={onCancel} disabled={pending}>cancel</Button><Button kind="danger" onClick={onConfirm} disabled={pending}>{pending ? <BrailleSpinner /> : 'yes, disable'}</Button></div>
  </section>
}
