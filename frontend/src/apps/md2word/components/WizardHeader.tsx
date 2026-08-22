import { Download, FileText, ListChecks, PencilLine } from 'lucide-react'

import { Button } from '../../../components/ui/button'
import type { WizardStep } from '../types'
import { wizardSteps } from '../utils'

const stepMeta: Record<WizardStep, { label: string; icon: typeof FileText }> = {
  1: { label: '上传文件', icon: FileText },
  2: { label: '查看预览', icon: PencilLine },
  3: { label: '选择模板', icon: ListChecks },
  4: { label: '生成下载', icon: Download },
}

export function WizardHeader({
  busy,
  step,
  clickableUntilGenerated,
  onReset,
  onGoToStep,
}: {
  busy: boolean
  step: WizardStep
  clickableUntilGenerated: boolean
  onReset: () => void
  onGoToStep: (step: WizardStep) => void
}) {
  return (
    <header>
      <div className="flex flex-col gap-4 px-6 pt-8 pb-0 lg:px-8">
        <div className="max-w-3xl space-y-4">
          <div className="space-y-3">
            <button
              type="button"
              className="text-left text-4xl font-semibold tracking-tight transition-opacity hover:opacity-70 disabled:opacity-100"
              onClick={onReset}
              disabled={busy}
            >
              MD2Word
            </button>
          </div>
        </div>
        <div className="h-px w-full bg-black" aria-hidden="true" />
        <div className="grid w-full grid-cols-4 gap-3">
          {wizardSteps.map((item) => {
            const clickable = !busy && item >= step && (item === 1 || clickableUntilGenerated)
            const { label, icon: Icon } = stepMeta[item]
            const active = item === step
            return (
              <Button
                key={item}
                type="button"
                variant="ghost"
                className="flex h-auto min-h-14 w-full items-center justify-start gap-3 rounded-none px-0 py-2 text-left shadow-none hover:bg-transparent hover:text-inherit"
                onClick={() => onGoToStep(item)}
                disabled={!clickable}
                aria-label={`返回第 ${item} 步`}
              >
                <span className={active ? 'flex size-9 items-center justify-center rounded-full bg-black' : 'flex size-9 items-center justify-center rounded-full bg-white'}>
                  <Icon className={active ? 'size-5 text-white' : 'size-5 text-black'} />
                </span>
                <span className={active ? 'text-sm leading-5 text-black' : 'text-sm leading-5 text-black/45'}>{label}</span>
              </Button>
            )
          })}
        </div>
      </div>
    </header>
  )
}
