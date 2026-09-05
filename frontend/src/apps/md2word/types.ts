export type TemplateItem = {
  id: string
  label: string
  notes: string
  ready: boolean
  family: string
  variant: string
  supports_cover: boolean
  supports_toc: boolean
  supports_subtitle: boolean
  preview: string
}

export type FormalizeResult = {
  title: string
  header_title: string
  output_name: string
  preview: string
  cleaned_markdown: string
  file_name: string
}

export type FormalizeStageEvent = {
  type: 'stage'
  step: string
  message: string
}

export type FormalizeCompleteEvent = {
  type: 'result'
  result: FormalizeResult
}

export type FormalizeStreamEvent = FormalizeStageEvent | FormalizeCompleteEvent

export type WizardStep = 1 | 2 | 3 | 4

export type ProcessingMode = 'baseline' | 'ai_enhanced'

export type ToastTone = 'info' | 'error'

export type ToastState = {
  text: string
  tone: ToastTone
} | null
