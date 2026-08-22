import type { WizardStep } from './types'

export function buildOutputName(title: string) {
  const stem = title.trim().replace(/[\\/:*?"<>|]+/g, '_') || 'output'
  return `${stem}.docx`
}

export const wizardSteps: WizardStep[] = [1, 2, 3, 4]
