import { RefreshCcw, Sparkles } from 'lucide-react'

import { Button } from '../../../components/ui/button'
import type { ToastState } from '../types'

export function WizardToast({
  toast,
  onClose,
}: {
  toast: ToastState
  onClose: () => void
}) {
  if (!toast) {
    return null
  }

  return (
    <div className="fixed inset-x-0 top-5 z-50 flex justify-center px-4" aria-live="polite" aria-atomic="true">
      <div className="flex w-full max-w-xl items-center justify-between gap-4 rounded-2xl bg-background px-4 py-3 text-foreground">
        <div className="flex items-center gap-3">
          {toast.tone === 'error' ? <RefreshCcw className="size-4" /> : <Sparkles className="size-4" />}
          <span className="text-sm">{toast.text}</span>
        </div>
        <Button type="button" variant="ghost" size="icon-sm" onClick={onClose} aria-label="关闭提示">
          ×
        </Button>
      </div>
    </div>
  )
}
