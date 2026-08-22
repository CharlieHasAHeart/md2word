import { ArrowRight, Check, Download, LoaderCircle } from 'lucide-react'

import { buttonVariants } from '../../../../components/ui/button'
import { cn } from '../../../../lib/utils'

export function ResultStep({
  busy,
  downloadName,
  downloadUrl,
}: {
  busy: boolean
  downloadName: string
  downloadUrl: string
}) {
  return (
    <section className="px-6 py-10 lg:px-8">
      <div className="flex flex-col items-center justify-center gap-8 text-center">
        <div className="flex items-center justify-center gap-3">
          {busy ? <LoaderCircle className="size-5 animate-spin" aria-hidden="true" /> : <Check className="size-5" aria-hidden="true" />}
          <h3 className="text-xl font-semibold tracking-tight">{busy ? '正在生成文档' : '文档已生成'}</h3>
        </div>
        <a
          className={cn(
            buttonVariants({ variant: 'default', size: 'lg' }),
            'w-full max-w-xs justify-center',
            (!downloadUrl || busy) && 'pointer-events-none opacity-50',
          )}
          href={!busy && downloadUrl ? downloadUrl : undefined}
          download={downloadName}
          aria-disabled={!downloadUrl || busy}
          onClick={(event) => {
            if (!downloadUrl || busy) {
              event.preventDefault()
            }
          }}
        >
          <Download className="mr-1 size-4" />
          下载 Word 文件
          <ArrowRight className="ml-1 size-4" />
        </a>
      </div>
    </section>
  )
}
