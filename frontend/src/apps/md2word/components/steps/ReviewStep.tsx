import { ArrowRight } from 'lucide-react'

import { Button } from '../../../../components/ui/button'
import { Textarea } from '../../../../components/ui/textarea'

export function ReviewStep({
  fileName,
  markdown,
  onMarkdownChange,
  onNext,
}: {
  fileName: string
  markdown: string
  onMarkdownChange: (value: string) => void
  onNext: () => void
}) {
  return (
    <section>
      <div className="px-6 pb-6 lg:px-8">
        <div className="space-y-2">
          <h3 className="text-xl font-semibold tracking-tight">整理后预览</h3>
          <p className="text-sm text-muted-foreground">{fileName}</p>
        </div>
      </div>
      <div className="px-6 pb-6 lg:px-8 lg:pb-8">
        <Textarea
          value={markdown}
          onChange={(event) => onMarkdownChange(event.target.value)}
          className="h-[28rem] resize-none overflow-auto rounded-2xl bg-muted/30 p-5 font-mono text-sm leading-6 text-foreground/90"
          placeholder="尚无预览内容"
          spellCheck={false}
        />
      </div>
      <div className="flex justify-end bg-muted/20 px-6 py-5 lg:px-8">
        <Button type="button" onClick={onNext}>
          下一步
          <ArrowRight className="ml-1 size-4" />
        </Button>
      </div>
    </section>
  )
}
