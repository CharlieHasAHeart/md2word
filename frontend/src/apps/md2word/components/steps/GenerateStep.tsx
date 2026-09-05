import { ArrowRight } from 'lucide-react'

import { Button } from '../../../../components/ui/button'
import { Input } from '../../../../components/ui/input'
import { Label } from '../../../../components/ui/label'
import type { ProcessingMode, TemplateItem } from '../../types'

export function GenerateStep({
  busy,
  title,
  outputName,
  selectedTemplate,
  subtitle,
  processingMode,
  onTitleChange,
  onOutputNameChange,
  onSubtitleChange,
  onProcessingModeChange,
  onGenerate,
}: {
  busy: boolean
  title: string
  outputName: string
  selectedTemplate: TemplateItem | undefined
  subtitle: string
  processingMode: ProcessingMode
  onTitleChange: (value: string) => void
  onOutputNameChange: (value: string) => void
  onSubtitleChange: (value: string) => void
  onProcessingModeChange: (value: ProcessingMode) => void
  onGenerate: () => void
}) {
  const outputNameValue = outputName.toLowerCase().endsWith('.docx')
    ? outputName.slice(0, -5)
    : outputName

  return (
    <section>
      <div className="px-6 pb-6 lg:px-8">
        <div className="space-y-2">
          <h3 className="text-xl font-semibold tracking-tight">生成下载</h3>
          <p className="text-sm text-muted-foreground">确认标题与输出信息，开始生成 Word 文件。</p>
        </div>
      </div>
      <div className="px-6 pb-6 lg:px-8 lg:pb-8">
        <div className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="doc-title">文档标题</Label>
            <Input id="doc-title" value={title} onChange={(event) => onTitleChange(event.target.value)} placeholder="封面标题" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="output-name">输出文件名</Label>
            <div className="flex items-center gap-3">
              <Input
                id="output-name"
                value={outputNameValue}
                onChange={(event) => onOutputNameChange(`${event.target.value}.docx`)}
                placeholder="output"
              />
              <span className="text-sm text-foreground/80">.docx</span>
            </div>
          </div>
          {selectedTemplate?.supports_subtitle ? (
            <div className="space-y-2">
              <Label htmlFor="subtitle">subtitle</Label>
              <Input
                id="subtitle"
                value={subtitle}
                onChange={(event) => onSubtitleChange(event.target.value)}
                placeholder="短模板可填写副标题"
              />
            </div>
          ) : null}
          <div className="space-y-2">
            <Label>转换模式</Label>
            <div className="flex flex-wrap gap-3">
              <Button
                type="button"
                variant={processingMode === 'baseline' ? 'default' : 'outline'}
                onClick={() => onProcessingModeChange('baseline')}
              >
                直接转换
              </Button>
              <Button
                type="button"
                variant={processingMode === 'ai_enhanced' ? 'default' : 'outline'}
                onClick={() => onProcessingModeChange('ai_enhanced')}
              >
                AI 增强后转换
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">
              {processingMode === 'baseline'
                ? '使用前 5 步基线清理结果直接生成 Word。'
                : '在基线清理后继续执行标题结构与 AI 痕迹清理，再生成 Word。'}
            </p>
          </div>
        </div>
      </div>
      <div className="flex justify-end bg-muted/20 px-6 py-5 lg:px-8">
        <Button type="button" onClick={onGenerate} disabled={!selectedTemplate?.ready || busy}>
          开始生成文档
          <ArrowRight className="ml-1 size-4" />
        </Button>
      </div>
    </section>
  )
}
