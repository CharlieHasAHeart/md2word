import { LoaderCircle, Upload } from 'lucide-react'

export function ImportStep({
  busy,
  fileName,
  analyzingName,
  formalizeStatus,
  onFileChange,
}: {
  busy: boolean
  fileName: string
  analyzingName: string
  formalizeStatus: string
  onFileChange: (file: File | null) => void
}) {
  return (
    <section>
      <div className="space-y-3 px-6 pb-6 lg:px-8">
        <h2 className="text-3xl font-semibold tracking-tight">导入 Markdown 文件</h2>
      </div>
      <div className="px-6 pb-6 lg:px-8 lg:pb-8">
        {busy && fileName ? (
          <div className="flex min-h-80 flex-col items-center justify-center rounded-2xl bg-muted/30 px-6 text-center">
            <LoaderCircle className="size-9 animate-spin" />
            <p className="mt-5 text-lg font-medium">{formalizeStatus || '正在整理 Markdown 文件'}</p>
            <p className="mt-2 text-sm text-muted-foreground">{analyzingName || fileName}</p>
          </div>
        ) : (
          <label className="group flex min-h-80 cursor-pointer flex-col items-center justify-center rounded-2xl bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.95),rgba(245,245,245,0.85))] px-6 text-center transition-colors hover:bg-muted/40">
            <input
              type="file"
              accept=".md,text/markdown,text/plain"
              className="sr-only"
              onClick={(event) => {
                event.currentTarget.value = ''
              }}
              onChange={(event) => {
                onFileChange(event.currentTarget.files?.[0] ?? null)
                event.currentTarget.value = ''
              }}
            />
            <div className="flex size-16 items-center justify-center rounded-full bg-background">
              <Upload className="size-6" />
            </div>
            <p className="mt-6 text-lg font-semibold">点击选择 Markdown 文件</p>
            <p className="mt-2 text-sm text-muted-foreground">支持 `.md`，导入后自动进入整理流程</p>
          </label>
        )}
      </div>
    </section>
  )
}
