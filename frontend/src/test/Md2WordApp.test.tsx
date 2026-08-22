import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Md2WordApp } from '../apps/md2word/Md2WordApp'

const templates = [
  { id: 'reference', label: '当前内置模板', notes: 'note', ready: true, family: 'builtin', variant: 'reference', supports_cover: true, supports_toc: true, supports_subtitle: false, preview: '/template-covers/reference.svg' },
  { id: 'cloudbility-short', label: 'Cloudbility 短版', notes: 'note', ready: true, family: 'cloudbility', variant: 'short', supports_cover: true, supports_toc: true, supports_subtitle: true, preview: '/template-covers/cloudbility-short.svg' },
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
    if (url.endsWith('/api/md2word/formalize')) {
      return makeJsonResponse({
        title: '测试标题',
        header_title: '测试标题',
        output_name: 'demo.docx',
        preview: '# 测试标题',
        cleaned_markdown: '# 测试标题',
        file_name: 'demo.md',
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

    await screen.findByText('整理后预览')
    fireEvent.click(screen.getByRole('button', { name: 'MD2Word' }))
    expect(screen.getByText('导入 Markdown 文件')).toBeInTheDocument()
  })

  test('generated file keeps previous steps locked after convert', async () => {
    installHappyFetch()
    render(<Md2WordApp />)
    chooseMarkdownFile()

    await screen.findByText('整理后预览')
    expect(screen.getByRole('button', { name: '返回第 2 步' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '返回第 3 步' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '返回第 4 步' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: '下一步' }))
    await screen.findByRole('heading', { name: '选择模板' })
    fireEvent.click(screen.getByRole('button', { name: '当前内置模板' }))
    await screen.findByRole('heading', { name: '生成下载' })

    fireEvent.click(screen.getByRole('button', { name: '开始生成文档' }))

    await waitFor(() => expect(screen.getByText('文档已生成')).toBeInTheDocument())
    const step2 = screen.getByRole('button', { name: '返回第 2 步' })
    const step3 = screen.getByRole('button', { name: '返回第 3 步' })
    const step4 = screen.getByRole('button', { name: '返回第 4 步' })

    expect(step2).toBeDisabled()
    expect(step3).toBeDisabled()
    expect(step4).toBeEnabled()
    expect(screen.getByText('文档已生成')).toBeInTheDocument()
  })

  test('generation keeps top progress buttons disabled while convert is in flight', async () => {
    let resolveConvert: ((value: Response) => void) | undefined
    const convertPromise = new Promise<Response>((resolve) => {
      resolveConvert = resolve
    })
    installHappyFetch({ convertPromise })
    render(<Md2WordApp />)
    chooseMarkdownFile()

    await screen.findByText('整理后预览')
    fireEvent.click(screen.getByRole('button', { name: '下一步' }))
    await screen.findByRole('heading', { name: '选择模板' })
    fireEvent.click(screen.getByRole('button', { name: '当前内置模板' }))
    await screen.findByRole('heading', { name: '生成下载' })
    fireEvent.click(screen.getByRole('button', { name: '开始生成文档' }))

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

  test('download uses utf8 filename from content disposition when available', async () => {
    const urlMock = installUrlMocks()
    const originalCreateElement = document.createElement.bind(document)
    let createdAnchor!: HTMLAnchorElement
    vi.spyOn(document, 'createElement').mockImplementation(((tagName: string) => {
      const element = originalCreateElement(tagName)
      if (tagName.toLowerCase() === 'a') {
        createdAnchor = element as HTMLAnchorElement
      }
      return element
    }) as typeof document.createElement)
    installHappyFetch({
      convertPromise: Promise.resolve(new Response(new Blob(['fake-docx']), {
        status: 200,
        headers: {
          'Content-Disposition': 'attachment; filename="_____ReacVer_____.docx"; filename*=UTF-8\'\'%E5%8F%AF%E9%AA%8C%E8%AF%81%E5%8F%8D%E5%BA%94%E5%8E%9F%E7%94%9F%E6%9D%90%E6%96%99%E6%A8%A1%E5%9E%8B%EF%BC%88ReacVer%EF%BC%89%E8%BD%AF%E4%BB%B6%E5%8C%96%E6%9E%84%E5%BB%BA%E6%96%B9%E6%A1%88.docx',
        },
      })),
    })
    render(<Md2WordApp />)
    chooseMarkdownFile()

    await screen.findByText('整理后预览')
    fireEvent.click(screen.getByRole('button', { name: '下一步' }))
    await screen.findByRole('heading', { name: '选择模板' })
    fireEvent.click(screen.getByRole('button', { name: '当前内置模板' }))
    await screen.findByRole('heading', { name: '生成下载' })
    fireEvent.click(screen.getByRole('button', { name: '开始生成文档' }))

    await waitFor(() => expect(urlMock.createObjectURL).toHaveBeenCalled())
    expect(createdAnchor.getAttribute('download')).toBe('可验证反应原生材料模型（ReacVer）软件化构建方案.docx')
  })

  test('error toast can be dismissed manually', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/md2word/templates')) {
        return makeJsonResponse(templates)
      }
      if (url.endsWith('/api/md2word/formalize')) {
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

  test('short template exposes subtitle input after selection', async () => {
    installHappyFetch()
    render(<Md2WordApp />)
    chooseMarkdownFile()

    await screen.findByText('整理后预览')
    fireEvent.click(screen.getByRole('button', { name: '下一步' }))
    await screen.findByRole('heading', { name: '选择模板' })

    fireEvent.click(screen.getByRole('button', { name: 'Cloudbility 短版' }))
    expect(screen.getByLabelText('subtitle')).toBeInTheDocument()
  })

  test('file input click clears previous value so same file can be selected again', () => {
    installHappyFetch()
    render(<Md2WordApp />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    Object.defineProperty(input, 'value', {
      configurable: true,
      writable: true,
      value: 'C:\\\\fakepath\\\\demo.md',
    })

    fireEvent.click(input)

    expect(input.value).toBe('')
  })
})
