import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'
import { UrlShortenerService } from './lib/urlStore'

function App() {
  const service = useMemo(() => {
    const instance = new UrlShortenerService()
    instance.load()
    return instance
  }, [])

  const [capacity, setCapacity] = useState(service.getCapacity())
  const [capacityInput, setCapacityInput] = useState('')
  const [longUrlInput, setLongUrlInput] = useState('')
  const [shortCodeInput, setShortCodeInput] = useState('')
  const [entries, setEntries] = useState(service.listAll())
  const [shortenResult, setShortenResult] = useState('')
  const [resolveResult, setResolveResult] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const hasProcessedRedirect = useRef(false)

  const refreshEntries = () => {
    setEntries(service.listAll())
  }

  const clearMessages = () => {
    setStatusMessage('')
    setErrorMessage('')
  }

  const buildShortUrl = (shortCode) => `${window.location.origin}/${shortCode}`

  const parseShortCodeInput = (value) => {
    const trimmed = value.trim()
    if (!trimmed) {
      throw new Error('Short code is required.')
    }

    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
      try {
        const parsed = new URL(trimmed)
        return parsed.pathname.replace(/^\/+/, '')
      } catch {
        throw new Error('Invalid short URL format.')
      }
    }

    return trimmed
  }

  const formatDateTime = (timestamp) =>
    new Date(timestamp).toLocaleString('ru-RU', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })

  const handleCapacitySubmit = (event) => {
    event.preventDefault()
    clearMessages()
    try {
      const parsed = Number.parseInt(capacityInput, 10)
      service.init(parsed)
      setCapacity(parsed)
      refreshEntries()
      setStatusMessage(`Вместимость установлена: ${parsed}`)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to initialize capacity.')
    }
  }

  const handleShortenSubmit = (event) => {
    event.preventDefault()
    clearMessages()
    setResolveResult('')
    try {
      const result = service.shorten(longUrlInput)
      setShortenResult(buildShortUrl(result.entry.shortCode))
      refreshEntries()
      if (result.isNew) {
        const evictedText = result.evicted
          ? ` Удалена запись: ${result.evicted.shortCode} (${result.evicted.longUrl}).`
          : ''
        setStatusMessage(`Короткая ссылка создана.${evictedText}`)
      } else {
        setStatusMessage('Возвращена существующая короткая ссылка для этого URL.')
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to shorten URL.')
    }
  }

  const handleResolveSubmit = (event) => {
    event.preventDefault()
    clearMessages()
    try {
      const shortCode = parseShortCodeInput(shortCodeInput)
      const entry = service.resolve(shortCode)
      setResolveResult(entry.longUrl)
      refreshEntries()
      setStatusMessage('Длинная ссылка успешно найдена, счетчик переходов обновлен.')
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to resolve short URL.')
    }
  }

  useEffect(() => {
    if (hasProcessedRedirect.current) {
      return
    }
    hasProcessedRedirect.current = true

    const pathCode = window.location.pathname.replace(/^\/+/, '')
    if (!pathCode) {
      return
    }

    try {
      const entry = service.resolve(pathCode)
      window.location.replace(entry.longUrl)
    } catch {
      // Unknown short code: keep showing the main UI.
    }
  }, [service])

  return (
    <main className="page">
      <h1>URL Shortener</h1>
      <p className="subtitle">Локальный сокращатель ссылок с политикой вытеснения LFU + FIFO.</p>

      {!capacity ? (
        <section className="card">
          <h2>Настройка вместимости</h2>
          <form onSubmit={handleCapacitySubmit} className="form">
            <label htmlFor="capacity-input">Количество URL в хранилище</label>
            <input
              id="capacity-input"
              type="number"
              min="1"
              step="1"
              value={capacityInput}
              onChange={(event) => setCapacityInput(event.target.value)}
              placeholder="Например, 100"
              required
            />
            <button type="submit">Запустить</button>
          </form>
        </section>
      ) : (
        <>
          <section className="card">
            <h2>Сократить URL</h2>
            <form onSubmit={handleShortenSubmit} className="form">
              <label htmlFor="long-url-input">Длинный URL</label>
              <input
                id="long-url-input"
                type="url"
                value={longUrlInput}
                onChange={(event) => setLongUrlInput(event.target.value)}
                placeholder="https://example.com/some/really/long/path"
                required
              />
              <button type="submit">Сократить</button>
            </form>
            {shortenResult && (
              <p className="result">
                Короткая ссылка: <a href={shortenResult}>{shortenResult}</a>
              </p>
            )}
          </section>

          <section className="card">
            <h2>Получить длинный URL</h2>
            <form onSubmit={handleResolveSubmit} className="form">
              <label htmlFor="short-code-input">Короткий код</label>
              <input
                id="short-code-input"
                type="text"
                value={shortCodeInput}
                onChange={(event) => setShortCodeInput(event.target.value)}
                placeholder="Введите shortCode"
                required
              />
              <button type="submit">Найти</button>
            </form>
            {resolveResult && (
              <p className="result">
                Длинный URL: <a href={resolveResult}>{resolveResult}</a>
              </p>
            )}
          </section>
        </>
      )}

      {statusMessage && <p className="status success">{statusMessage}</p>}
      {errorMessage && <p className="status error">{errorMessage}</p>}

      <section className="card">
        <h2>Сохраненные ссылки</h2>
        <p className="meta">
          Вместимость: <strong>{capacity ?? 'не задана'}</strong> | Хранится записей:{' '}
          <strong>{entries.length}</strong>
        </p>
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>Short</th>
                <th>Long URL</th>
                <th>Hits</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 ? (
                <tr>
                  <td colSpan="4" className="empty">
                    Пока нет записей
                  </td>
                </tr>
              ) : (
                entries.map((entry) => (
                  <tr key={entry.id}>
                    <td>
                      <a href={buildShortUrl(entry.shortCode)}>
                        <code>{buildShortUrl(entry.shortCode)}</code>
                      </a>
                    </td>
                    <td className="longCell">
                      <a href={entry.longUrl}>{entry.longUrl}</a>
                    </td>
                    <td>{entry.hitCount}</td>
                    <td>{formatDateTime(entry.createdAt)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}

export default App
