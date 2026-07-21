import { useEffect, useMemo, useRef, useState } from 'react'

type TemplateItem = {
  id: string
  label: string
  notes: string
  ready: boolean
  family: string
  variant: string
  supports_cover: boolean
  supports_toc: boolean
  preview: string
}

type AnalyzeResult = {
  title: string
  header_title: string
  output_name: string
  preview: string
  cleaned_markdown: string
  file_name: string
  subtitle: string
}

type WizardStep = 1 | 2 | 3 | 4

type ToastTone = 'info' | 'error'

type ToastState = {
  text: string
  tone: ToastTone
} | null

export function Md2WordApp() {
  const [templates, setTemplates] = useState<TemplateItem[]>([])
  const [templateId, setTemplateId] = useState('reference')
  const [title, setTitle] = useState('')
  const [headerTitle, setHeaderTitle] = useState('')
  const [outputName, setOutputName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [cleanedMarkdown, setCleanedMarkdown] = useState('')
  const [toast, setToast] = useState<ToastState>(null)
  const [busy, setBusy] = useState(false)
  const [step, setStep] = useState<WizardStep>(1)
  const [downloadUrl, setDownloadUrl] = useState('')
  const [downloadName, setDownloadName] = useState('result.docx')
  const [analyzingName, setAnalyzingName] = useState('')
  const toastTimerRef = useRef<number | null>(null)

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
    setHeaderTitle('')
    setOutputName('')
    setFile(null)
    setPreview('')
    setCleanedMarkdown('')
    hideToast()
    setBusy(false)
    setStep(1)
    setDownloadName('result.docx')
    setAnalyzingName('')
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
      .then((data: TemplateItem[]) => {
        setTemplates(data)
        if (data.length > 0) {
          setTemplateId(data[0].id)
        }
      })
      .catch(() => showToast('模板列表加载失败', 'error'))
  }, [])

  const selectedTemplate = useMemo(
    () => templates.find((item) => item.id === templateId),
    [templates, templateId],
  )

  const hasGeneratedFile = Boolean(downloadUrl)
  const canReviewGenerated = hasGeneratedFile && !busy

  function goToProgressStep(target: WizardStep) {
    if (busy || target === step) {
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

  function moveGeneratedStep(direction: -1 | 1) {
    if (!canReviewGenerated) {
      return
    }
    if (direction < 0 && step > 2) {
      setStep((step - 1) as WizardStep)
    }
    if (direction > 0 && step < 4) {
      setStep((step + 1) as WizardStep)
    }
  }

  async function analyzeFile(nextFile: File) {
    setBusy(true)
    hideToast()
    const formData = new FormData()
    formData.append('markdown_file', nextFile)

    try {
      const response = await fetch('/api/md2word/analyze', {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) {
        const payload = await response.json().catch(() => ({ detail: '整理失败' }))
        throw new Error(payload.detail || '整理失败')
      }
      const result = (await response.json()) as AnalyzeResult
      setTitle(result.title)
      setHeaderTitle(result.header_title)
      setOutputName(result.output_name)
      setPreview(result.preview || '文件为空')
      setCleanedMarkdown(result.cleaned_markdown || result.preview || '')
      setStep(2)
      hideToast()
      setAnalyzingName('')
    } catch (error) {
      setAnalyzingName('')
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
      setStep(1)
      return
    }
    setAnalyzingName(nextFile.name)
    setStep(1)
    await analyzeFile(nextFile)
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
    const markdownForConversion = cleanedMarkdown || preview
    const cleanedFile = new File([markdownForConversion], file.name || 'input.md', {
      type: file.type || 'text/markdown',
    })
    formData.append('markdown_file', cleanedFile)
    formData.append('template_id', effectiveTemplateId)
    formData.append('title', title)
    formData.append('header_title', headerTitle)
    formData.append('output_name', outputName)

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
      const match = disposition.match(/filename="?([^"]+)"?/)
      const filename = match?.[1] || outputName || 'result.docx'
      const url = URL.createObjectURL(blob)
      setDownloadUrl(url)
      setDownloadName(filename)
      hideToast()
    } catch (error) {
      showToast(error instanceof Error ? error.message : '生成失败', 'error')
    } finally {
      setBusy(false)
    }
  }

  function renderStepShell(content: JSX.Element, leftArrow?: JSX.Element | null, rightArrow?: JSX.Element | null) {
    const contentNode = <div className="step-shell-content">{content}</div>
    if (!canReviewGenerated) {
      return <div className="step-shell">{contentNode}</div>
    }
    return (
      <div className="step-shell with-arrows">
        {leftArrow ?? <button type="button" className="step-arrow hidden" aria-hidden="true" tabIndex={-1}>‹</button>}
        {contentNode}
        {rightArrow ?? <button type="button" className="step-arrow hidden" aria-hidden="true" tabIndex={-1}>›</button>}
      </div>
    )
  }

  function renderStep() {
    if (step === 1) {
      return (
        <div className="wizard-stage wizard-dropzone-stage">
          <div className="dropzone-card">
            <div className="dropzone-copy">
              <p className="eyebrow">Step 1</p>
              <h2>导入 Markdown 文件</h2>
              <p>将文档拖入或选择文件，系统会先整理 Markdown 语法并生成预览。</p>
            </div>
            {busy && file ? (
              <div className="dropzone-box loading" aria-live="polite" aria-busy="true">
                <span className="dropzone-spinner" />
                <span className="dropzone-title">正在整理 Markdown 文件</span>
                <span className="dropzone-subtitle">{analyzingName || file.name}</span>
                <span className="dropzone-loading-copy">请稍候，系统正在清理语法、检查格式并提取文档信息。</span>
              </div>
            ) : (
              <label className="dropzone-box">
                <input
                  type="file"
                  accept=".md,text/markdown,text/plain"
                  onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
                />
                <span className="dropzone-icon">.md</span>
                <span className="dropzone-title">点击选择 Markdown 文件</span>
                <span className="dropzone-subtitle">支持 `.md`，导入后自动进入整理流程</span>
              </label>
            )}
          </div>
        </div>
      )
    }

    if (step === 2) {
      return (
        <div className="wizard-stage">
          {renderStepShell(
            <div className="wizard-card-grid step-two-layout">
              <section className="panel-card wizard-card preview-side">
                <div className="preview-header">
                  <h3>整理后预览</h3>
                  <span>{file?.name || ''}</span>
                </div>
                <pre>{preview || '尚无预览内容'}</pre>
              </section>
              <section className="panel-card wizard-card info-side">
                <div className="step-tag">Step 2</div>
                <h3>确认文档信息</h3>
                <div className="field-grid single-column">
                  <label className="field">
                    <span>title</span>
                    <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="封面标题" />
                  </label>
                  <label className="field">
                    <span>页眉</span>
                    <input value={headerTitle} onChange={(event) => setHeaderTitle(event.target.value)} placeholder="页眉标题" />
                  </label>
                  <label className="field">
                    <span>输出文件名</span>
                    <input value={outputName} onChange={(event) => setOutputName(event.target.value)} placeholder="例如 result.docx" />
                  </label>
                </div>
                <div className="wizard-actions">
                  <button type="button" className="ghost-button" onClick={resetWizard}>返回上一步</button>
                  <button type="button" onClick={() => setStep(3)}>下一步：选择模板</button>
                </div>
              </section>
            </div>,
            null,
            canReviewGenerated ? (
              <button type="button" className="step-arrow" onClick={() => moveGeneratedStep(1)} aria-label="前往第三步">›</button>
            ) : null,
          )}
        </div>
      )
    }

    if (step === 3) {
      return (
        <div className="wizard-stage">
          {renderStepShell(
            <div className="panel-card template-stage-card">
              <div className="template-stage-header">
                <div>
                  <div className="step-tag">Step 3</div>
                  <h3>选择模板</h3>
                  <p>悬浮到模板卡片时可直接使用该模板开始转换。</p>
                </div>
                <div className="wizard-actions compact">
                  <button type="button" className="ghost-button" onClick={() => setStep(2)}>返回修改信息</button>
                </div>
              </div>
              <div className="template-card-grid">
                {templates.map((item) => (
                  <div
                    key={item.id}
                    className={!item.ready || busy ? 'template-card disabled' : 'template-card'}
                  >
                    <div className="template-cover-frame">
                      <img src={item.preview} alt={item.label} />
                    </div>
                    <div className="template-card-body">
                      <div className="template-card-topline">
                        <strong>{item.label}</strong>
                        <span className={item.ready ? 'status-chip ready' : 'status-chip missing'}>
                          {item.ready ? '可用' : '缺失'}
                        </span>
                      </div>
                      <div className="template-meta-row">
                        <span>{item.variant === 'long' ? '长版' : item.variant === 'short' ? '短版' : '默认'}</span>
                        {item.supports_cover ? <span>封面</span> : null}
                        {item.supports_toc ? <span>目录</span> : null}
                      </div>
                      <p>{item.notes}</p>
                      <div className="template-card-cta-wrap">
                        <button
                          type="button"
                          className="template-card-cta"
                          onClick={(event) => {
                            event.stopPropagation()
                            setTemplateId(item.id)
                            void onGenerate(item.id)
                          }}
                          disabled={!item.ready || busy}
                        >
                          使用此模板
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>,
            canReviewGenerated ? (
              <button type="button" className="step-arrow" onClick={() => moveGeneratedStep(-1)} aria-label="前往第二步">‹</button>
            ) : null,
            canReviewGenerated ? (
              <button type="button" className="step-arrow" onClick={() => moveGeneratedStep(1)} aria-label="前往第四步">›</button>
            ) : null,
          )}
        </div>
      )
    }

    return (
      <div className="wizard-stage">
        {renderStepShell(
          <div className="panel-card result-card">
            <div className="step-tag">Step 4</div>
            <div className="result-heading-row">
              {busy ? <span className="result-spinner" aria-hidden="true" /> : null}
              <h3>{busy ? '正在生成文档' : '文档已生成'}</h3>
            </div>
            <p>{busy ? '请稍候，系统正在套用模板并生成 Word 文件。' : '生成完成后，可直接下载结果文件。'}</p>
            <div className="result-actions">
              <button type="button" className="ghost-button" onClick={() => setStep(3)} disabled={busy}>返回模板选择</button>
              <a
                className={!downloadUrl || busy ? 'download-button disabled' : 'download-button'}
                href={!busy && downloadUrl ? downloadUrl : undefined}
                download={downloadName}
                aria-disabled={!downloadUrl || busy}
                onClick={(event) => {
                  if (!downloadUrl || busy) {
                    event.preventDefault()
                  }
                }}
              >
                下载 Word 文件
              </a>
            </div>
            {selectedTemplate ? <div className="result-template-note">当前模板：{selectedTemplate.label}</div> : null}
          </div>,
          canReviewGenerated ? (
            <button type="button" className="step-arrow" onClick={() => moveGeneratedStep(-1)} aria-label="前往第三步">‹</button>
          ) : null,
          null,
        )}
      </div>
    )
  }

  return (
    <section className="md2word-panel wizard-shell">
      <header className="panel-header wizard-header">
        <div>
          <button type="button" className="brand-reset" onClick={resetWizard} disabled={busy}>MD2Word</button>
          <p className="subline">导入 Markdown、确认文档信息、选择模板，然后下载生成好的 Word 文件。</p>
        </div>
        <div className="wizard-progress">
          {[1, 2, 3, 4].map((item) => {
            const target = item as WizardStep
            const clickable = !busy && (target === 1 || (hasGeneratedFile && target >= 2 && target <= 4))
            return (
              <button
                key={item}
                type="button"
                className={item <= step ? 'progress-node active' : 'progress-node'}
                onClick={() => goToProgressStep(target)}
                disabled={!clickable}
                aria-label={`返回第 ${item} 步`}
              >
                {item}
              </button>
            )
          })}
        </div>
      </header>
      {toast ? (
        <div className="toast-layer" aria-live="polite" aria-atomic="true">
          <div className={`toast toast-${toast.tone}`}>
            <span>{toast.text}</span>
            <button type="button" className="toast-close" onClick={hideToast} aria-label="关闭提示">
              ×
            </button>
          </div>
        </div>
      ) : null}
      {renderStep()}
    </section>
  )
}
