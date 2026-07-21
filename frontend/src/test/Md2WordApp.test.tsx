import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Md2WordApp } from '../apps/md2word/Md2WordApp'

const templates = [
  { id: 'reference', label: '当前内置模板', notes: 'note', ready: true, family: 'builtin', variant: 'reference', supports_cover: true, supports_toc: true, preview: '/template-covers/reference.svg' },
  { id: 'cloudbility-long', label: 'Cloudbility 长版', notes: 'note', ready: true, family: 'cloudbility', variant: 'long', supports_cover: true, supports_toc: true, preview: '/template-covers/cloudbility-long.svg' },
]

function makeJsonResponse(data: unknown) {
  return Promise.resolve(new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } }))
}

function installUrlMocks() {
  const original = globalThis.URL
  const urlMock = class extends original {}
  urlMock.createObjectURL = vi.fn(() => 'blob:test')
  urlMock.revokeObjectURL = vi.fn()
  vi.stubGlobal('URL', urlMock)
  return urlMock
}

function installHappyFetch(options?: { convertPromise?: Promise<Response> }) {
  const convertPromise = options?.convertPromise
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith('/api/md2word/templates')) {
      return makeJsonResponse(templates)
    }
    if (url.endsWith('/api/md2word/analyze')) {
      return makeJsonResponse({
        title: '测试标题',
        header_title: '测试标题',
        output_name: 'demo.docx',
        preview: '# 测试标题',
        cleaned_markdown: '# 测试标题',
        file_name: 'demo.md',
        subtitle: '',
      })
    }
    if (url.endsWith('/api/md2word/convert')) {
      return convertPromise ?? Promise.resolve(new Response(new Blob(['fake-docx']), {
        status: 200,
        headers: { 'Content-Disposition': 'attachment; filename="demo.docx"' },
      }))
    }
    return Promise.reject(new Error('unexpected request'))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function chooseMarkdownFile() {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  const file = new File(['# hello'], 'demo.md', { type: 'text/markdown' })
  fireEvent.change(input, { target: { files: [file] } })
}

describe('Md2WordApp', () => {
  beforeEach(() => {
    installUrlMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  test('step 1 reset entry clears back to import page', async () => {
    installHappyFetch()
    render(<Md2WordApp />)
    chooseMarkdownFile()

    await screen.findByText('确认文档信息')
    fireEvent.click(screen.getByRole('button', { name: 'MD2Word' }))
    expect(screen.getByText('导入 Markdown 文件')).toBeInTheDocument()
  })

  test('generated file allows navigation among steps 2 3 4 only after convert', async () => {
    installHappyFetch()
    render(<Md2WordApp />)
    chooseMarkdownFile()

    await screen.findByText('确认文档信息')
    expect(screen.getByRole('button', { name: '返回第 2 步' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '返回第 3 步' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '返回第 4 步' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: '下一步：选择模板' }))
    await screen.findByText('选择模板')

    const useButtons = screen.getAllByRole('button', { name: '使用此模板' })
    fireEvent.click(useButtons[0])

    await waitFor(() => expect(screen.getByText('文档已生成')).toBeInTheDocument())
    const step2 = screen.getByRole('button', { name: '返回第 2 步' })
    const step3 = screen.getByRole('button', { name: '返回第 3 步' })
    const step4 = screen.getByRole('button', { name: '返回第 4 步' })

    expect(step2).toBeEnabled()
    expect(step3).toBeEnabled()
    expect(step4).toBeEnabled()

    fireEvent.click(step3)
    expect(screen.getByText('选择模板')).toBeInTheDocument()
    fireEvent.click(step2)
    expect(screen.getByText('确认文档信息')).toBeInTheDocument()
  })

  test('generation keeps top progress buttons disabled while convert is in flight', async () => {
    let resolveConvert: ((value: Response) => void) | undefined
    const convertPromise = new Promise<Response>((resolve) => {
      resolveConvert = resolve
    })
    installHappyFetch({ convertPromise })
    render(<Md2WordApp />)
    chooseMarkdownFile()

    await screen.findByText('确认文档信息')
    fireEvent.click(screen.getByRole('button', { name: '下一步：选择模板' }))
    await screen.findByText('选择模板')
    fireEvent.click(screen.getAllByRole('button', { name: '使用此模板' })[0])

    await screen.findByText('正在生成文档')
    expect(screen.getByRole('button', { name: '返回第 1 步' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '返回第 2 步' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '返回第 3 步' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '返回第 4 步' })).toBeDisabled()

    resolveConvert?.(new Response(new Blob(['fake-docx']), {
      status: 200,
      headers: { 'Content-Disposition': 'attachment; filename="demo.docx"' },
    }))

    await waitFor(() => expect(screen.getByText('文档已生成')).toBeInTheDocument())
  })

  test('step arrows only appear after a file has been generated', async () => {
    installHappyFetch()
    render(<Md2WordApp />)
    chooseMarkdownFile()

    await screen.findByText('确认文档信息')
    expect(screen.queryByLabelText('前往第三步')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '下一步：选择模板' }))
    await screen.findByText('选择模板')
    fireEvent.click(screen.getAllByRole('button', { name: '使用此模板' })[0])

    await waitFor(() => expect(screen.getByLabelText('前往第三步')).toBeInTheDocument())
    fireEvent.click(screen.getByLabelText('前往第三步'))
    expect(screen.getByText('选择模板')).toBeInTheDocument()
  })

  test('error toast can be dismissed manually', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/md2word/templates')) {
        return makeJsonResponse(templates)
      }
      if (url.endsWith('/api/md2word/analyze')) {
        return Promise.resolve(new Response(JSON.stringify({ detail: '整理失败' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }))
      }
      return Promise.reject(new Error('unexpected request'))
    }))

    render(<Md2WordApp />)
    chooseMarkdownFile()

    await screen.findByText('整理失败')
    fireEvent.click(screen.getByRole('button', { name: '关闭提示' }))
    await waitFor(() => expect(screen.queryByText('整理失败')).not.toBeInTheDocument())
  })
})
