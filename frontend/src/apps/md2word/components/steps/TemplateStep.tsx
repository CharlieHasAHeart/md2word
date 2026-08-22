import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../../../components/ui/tooltip'
import { cn } from '../../../../lib/utils'
import type { TemplateItem } from '../../types'

export function TemplateStep({
  templates,
  selectedTemplate,
  templateId,
  busy,
  onSelectTemplate,
}: {
  templates: TemplateItem[]
  selectedTemplate: TemplateItem | undefined
  templateId: string
  busy: boolean
  onSelectTemplate: (id: string) => void
}) {
  return (
    <section>
      <div className="px-6 pb-6 lg:px-8">
        <div className="space-y-3">
          <div className="space-y-2">
            <h3 className="text-xl font-semibold tracking-tight">选择模板</h3>
            <p className="text-sm text-muted-foreground">选择模板并确认文档信息</p>
          </div>
        </div>
      </div>
      <div className="px-6 pb-6 lg:px-8 lg:pb-8">
        <TooltipProvider>
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
            {templates.map((item) => {
              const previewButton = (
                <button
                  type="button"
                  className={cn(
                    'group min-w-0 overflow-hidden bg-transparent text-left transition-all',
                    item.ready && !busy ? '' : 'opacity-60',
                  )}
                  onClick={() => onSelectTemplate(item.id)}
                  disabled={!item.ready || busy}
                  aria-label={item.label}
                >
                  <div className="flex h-[18rem] items-center justify-center overflow-hidden">
                    <img src={item.preview} alt={item.label} className="h-full w-full object-contain transition-transform duration-300 group-hover:scale-[1.02]" />
                  </div>
                </button>
              )

              return (
                <Tooltip key={item.id}>
                  <TooltipTrigger render={previewButton} />
                  <TooltipContent sideOffset={8}>{item.label}</TooltipContent>
                </Tooltip>
              )
            })}
          </div>
          </div>
        </TooltipProvider>
      </div>
    </section>
  )
}
