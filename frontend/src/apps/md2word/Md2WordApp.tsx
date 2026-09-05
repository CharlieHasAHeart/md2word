import { useEffect, useMemo, useRef, useState } from 'react'

import { WizardHeader } from './components/WizardHeader'
import { WizardToast } from './components/WizardToast'
import { GenerateStep } from './components/steps/GenerateStep'
import { ImportStep } from './components/steps/ImportStep'
import { ResultStep } from './components/steps/ResultStep'
import { ReviewStep } from './components/steps/ReviewStep'
import { TemplateStep } from './components/steps/TemplateStep'
import type { FormalizeResult, FormalizeStreamEvent, ProcessingMode, TemplateItem, ToastState, ToastTone, WizardStep } from './types'
import { buildOutputName } from './utils'

const INITIAL_FORMALIZE_STATUS = '正在清理转义符号'

export function Md2WordApp() {
  const [templates, setTemplates] = useState<TemplateItem[]>([])
  const [templateId, setTemplateId] = useState('reference')
  const [title, setTitle] = useState('')
  const [outputName, setOutputName] = useState('result.docx')
  const [outputNameEdited, setOutputNameEdited] = useState(false)
  const [subtitle, setSubtitle] = useState('')
  const [processingMode, setProcessingMode] = useState<ProcessingMode>('baseline')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [cleanedMarkdown, setCleanedMarkdown] = useState('')
  const [toast, setToast] = useState<ToastState>(null)
  const [busy, setBusy] = useState(false)
  const [step, setStep] = useState<WizardStep>(1)
  const [downloadUrl, setDownloadUrl] = useState('')
  const [downloadName, setDownloadName] = useState('result.docx')
  const [analyzingName, setAnalyzingName] = useState('')
  const [formalizeStatus, setFormalizeStatus] = useState('')
  const toastTimerRef = useRef<number | null>(null)

  const selectedTemplate = useMemo(
    () => templates.find((item) => item.id === templateId),
    [templates, templateId],
  )
  const headerTitle = title.trim()
  const hasGeneratedFile = Boolean(downloadUrl)
  const canReviewGenerated = hasGeneratedFile && !busy

  function showToast(text: string, tone: ToastTone = 'info', duration = 3200) {
    if (toastTimerRef.current) {
      window.clearTimeout(toastTimerRef.current)
      toastTimerRef.current = null
    }
    setToast({ text, tone })
    if (duration > 0) {
      toastTimerRef.current = window.setTimeout(() => {
        setToast(null)
        toastTimerRef.current = null
      }, duration)
    }
  }

  function hideToast() {
    if (toastTimerRef.current) {
      window.clearTimeout(toastTimerRef.current)
      toastTimerRef.current = null
    }
    setToast(null)
  }

  function clearDownloadUrl() {
    if (downloadUrl) {
      URL.revokeObjectURL(downloadUrl)
      setDownloadUrl('')
    }
  }

  function resetWizard() {
    clearDownloadUrl()
    setTemplateId('reference')
    setTitle('')
    setOutputName('result.docx')
    setOutputNameEdited(false)
    setSubtitle('')
    setProcessingMode('baseline')
    setFile(null)
    setPreview('')
    setCleanedMarkdown('')
    hideToast()
    setBusy(false)
    setStep(1)
    setDownloadName('result.docx')
    setAnalyzingName('')
    setFormalizeStatus('')
  }

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) {
        window.clearTimeout(toastTimerRef.current)
      }
      if (downloadUrl) {
        URL.revokeObjectURL(downloadUrl)
      }
    }
  }, [downloadUrl])

  useEffect(() => {
    fetch('/api/md2word/templates')
      .then((response) => response.json())
      .then((data: unknown) => {
        const normalized = Array.isArray(data) ? (data as TemplateItem[]) : []
        setTemplates(normalized)
        if (normalized.length > 0) {
          setTemplateId(normalized[0].id)
        }
      })
      .catch(() => showToast('模板列表加载失败', 'error'))
  }, [])

  function goToProgressStep(target: WizardStep) {
    if (busy || target === step) {
      return
    }
    if (target < step) {
      return
    }
    if (target === 1) {
      resetWizard()
      return
    }
    if (canReviewGenerated && target >= 2 && target <= 4) {
      setStep(target)
    }
  }

  async function formalizeFile(nextFile: File) {
    setBusy(true)
    hideToast()
    setFormalizeStatus(INITIAL_FORMALIZE_STATUS)
    const formData = new FormData()
    formData.append('markdown_file', nextFile)

    try {
      const response = await fetch('/api/md2word/formalize', {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        const payload = await response.json().catch(() => ({ detail: '整理失败' }))
        throw new Error(payload.detail || '整理失败')
      }
      const result = await readFormalizeResult(response, setFormalizeStatus)
      setTitle(result.title)
      setOutputName(result.output_name || buildOutputName(result.title))
      setOutputNameEdited(false)
      setSubtitle('')
      setPreview(result.preview ?? '文件为空')
      setCleanedMarkdown(result.cleaned_markdown ?? result.preview ?? '')
      setStep(2)
      hideToast()
      setAnalyzingName('')
      setFormalizeStatus('')
    } catch (error) {
      setAnalyzingName('')
      setFormalizeStatus('')
      showToast(error instanceof Error ? error.message : '整理失败', 'error')
    } finally {
      setBusy(false)
    }
  }

  async function onFileChange(nextFile: File | null) {
    setFile(nextFile)
    clearDownloadUrl()
    if (!nextFile) {
      setPreview('')
      setCleanedMarkdown('')
      setAnalyzingName('')
      setFormalizeStatus('')
      setStep(1)
      return
    }
    setAnalyzingName(nextFile.name)
    setStep(1)
    await formalizeFile(nextFile)
  }

  async function onGenerate(nextTemplateId?: string) {
    if (!file) {
      showToast('请选择 Markdown 文件', 'error')
      return
    }
    const effectiveTemplateId = nextTemplateId || templateId
    clearDownloadUrl()
    setBusy(true)
    setStep(4)
    hideToast()
    const formData = new FormData()
    const markdownForConversion = cleanedMarkdown
    const cleanedFile = new File([markdownForConversion], file.name || 'input.md', {
      type: file.type || 'text/markdown',
    })
    formData.append('markdown_file', cleanedFile)
    formData.append('template_id', effectiveTemplateId)
    formData.append('title', title)
    formData.append('header_title', headerTitle)
    formData.append('output_name', outputName || buildOutputName(title))
    formData.append('mode', processingMode)
    if (selectedTemplate?.supports_subtitle && subtitle.trim()) {
      formData.append('subtitle', subtitle.trim())
    }

    try {
      const response = await fetch('/api/md2word/convert', {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        const payload = await response.json().catch(() => ({ detail: '生成失败' }))
        throw new Error(payload.detail || '生成失败')
      }
      const blob = await response.blob()
      const disposition = response.headers.get('Content-Disposition') || ''
      const filename = parseDownloadFilename(disposition) || outputName || buildOutputName(title)
      const url = URL.createObjectURL(blob)
      setDownloadUrl(url)
      setDownloadName(filename)
      triggerBrowserDownload(url, filename)
      hideToast()
    } catch (error) {
      showToast(error instanceof Error ? error.message : '生成失败', 'error')
    } finally {
      setBusy(false)
    }
  }

  function handleTitleChange(nextTitle: string) {
    setTitle(nextTitle)
    if (!outputNameEdited) {
      setOutputName(buildOutputName(nextTitle))
    }
  }

  function handleOutputNameChange(nextOutputName: string) {
    setOutputName(nextOutputName)
    setOutputNameEdited(true)
  }

  function renderCurrentStep() {
    if (step === 1) {
      return (
        <ImportStep
          busy={busy}
          fileName={file?.name || ''}
          analyzingName={analyzingName}
          formalizeStatus={formalizeStatus}
          onFileChange={onFileChange}
        />
      )
    }

    if (step === 2) {
      return (
        <ReviewStep
          fileName={file?.name || ''}
          markdown={cleanedMarkdown}
          onMarkdownChange={setCleanedMarkdown}
          onNext={() => setStep(3)}
        />
      )
    }

    if (step === 3) {
      return (
        <TemplateStep
          templates={templates}
          selectedTemplate={selectedTemplate}
          templateId={templateId}
          busy={busy}
          onSelectTemplate={(id) => {
            setTemplateId(id)
            setStep(4)
          }}
        />
      )
    }

    return (
      busy || hasGeneratedFile ? (
        <ResultStep
          busy={busy}
          downloadName={downloadName}
          downloadUrl={downloadUrl}
        />
      ) : (
        <GenerateStep
          busy={busy}
          title={title}
          outputName={outputName}
          selectedTemplate={selectedTemplate}
          subtitle={subtitle}
          processingMode={processingMode}
          onTitleChange={handleTitleChange}
          onOutputNameChange={handleOutputNameChange}
          onSubtitleChange={setSubtitle}
          onProcessingModeChange={setProcessingMode}
          onGenerate={() => void onGenerate()}
        />
      )
    )
  }

  return (
    <section className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <WizardHeader
        busy={busy}
        step={step}
        clickableUntilGenerated={hasGeneratedFile && !busy}
        onReset={resetWizard}
        onGoToStep={goToProgressStep}
      />
      <WizardToast toast={toast} onClose={hideToast} />
      <div>{renderCurrentStep()}</div>
    </section>
  )
}

async function readFormalizeResult(
  response: Response,
  onStageChange: (message: string) => void,
): Promise<FormalizeResult> {
  const contentType = response.headers.get('Content-Type') || ''
  if (!contentType.includes('application/x-ndjson') || !response.body) {
    return (await response.json()) as FormalizeResult
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: FormalizeResult | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    const parsed = consumeFormalizeLines(buffer)
    buffer = parsed.remainder
    for (const event of parsed.events) {
      if (event.type === 'stage') {
        onStageChange(event.message)
        continue
      }
      result = event.result
    }
  }

  buffer += decoder.decode()
  const parsed = consumeFormalizeLines(buffer)
  for (const event of parsed.events) {
    if (event.type === 'stage') {
      onStageChange(event.message)
      continue
    }
    result = event.result
  }

  if (result === null) {
    throw new Error('整理失败')
  }
  return result
}

function consumeFormalizeLines(buffer: string): { events: FormalizeStreamEvent[]; remainder: string } {
  const lines = buffer.split('\n')
  const remainder = lines.pop() ?? ''
  const events = lines
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line) as FormalizeStreamEvent)
  return { events, remainder }
}

function triggerBrowserDownload(url: string, filename: string) {
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.style.display = 'none'
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
}

function parseDownloadFilename(contentDisposition: string): string {
  const utf8Match = contentDisposition.match(/filename\*\s*=\s*UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      // Fall back to the ASCII filename parameter below.
    }
  }

  const asciiMatch = contentDisposition.match(/filename\s*=\s*"([^"]+)"|filename\s*=\s*([^;]+)/i)
  const asciiName = asciiMatch?.[1] || asciiMatch?.[2]
  return asciiName?.trim() || ''
}
