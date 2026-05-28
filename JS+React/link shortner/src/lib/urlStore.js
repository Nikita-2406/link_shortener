
export class UrlEntry {
  /**
   * @param {object} params
   * @param {string} params.id
   * @param {string} params.longUrl
   * @param {string} params.shortCode
   * @param {number} params.hitCount
   * @param {number} params.createdAt
   */
  constructor({ id, longUrl, shortCode, hitCount, createdAt }) {
    this.id = id
    this.longUrl = longUrl
    this.shortCode = shortCode
    this.hitCount = hitCount
    this.createdAt = createdAt
  }


  incrementHits() {
    this.hitCount += 1
  }

  /**
   * @returns {{id: string, longUrl: string, shortCode: string, hitCount: number, createdAt: number}}
   */
  toJSON() {
    return {
      id: this.id,
      longUrl: this.longUrl,
      shortCode: this.shortCode,
      hitCount: this.hitCount,
      createdAt: this.createdAt,
    }
  }

  /**
   * @param {unknown} raw
   * @returns {UrlEntry | null}
   */
  static fromJSON(raw) {
    if (!raw || typeof raw !== 'object') {
      return null
    }

    const candidate = /** @type {Record<string, unknown>} */ (raw)
    const { id, longUrl, shortCode, hitCount, createdAt } = candidate
    if (
      typeof id !== 'string' ||
      typeof longUrl !== 'string' ||
      typeof shortCode !== 'string' ||
      typeof hitCount !== 'number' ||
      typeof createdAt !== 'number'
    ) {
      return null
    }

    return new UrlEntry({ id, longUrl, shortCode, hitCount, createdAt })
  }
}


export class UrlRepository {
  /**
   * @param {string} storageKey
   */
  constructor(storageKey = 'link_shortener_store_v1') {
    this.storageKey = storageKey
  }

  /**
   * @returns {{capacity: number | null, entries: UrlEntry[]}}
   */
  load() {
    const rawData = localStorage.getItem(this.storageKey)
    if (!rawData) {
      return { capacity: null, entries: [] }
    }

    try {
      const parsed = JSON.parse(rawData)
      if (!parsed || typeof parsed !== 'object') {
        return { capacity: null, entries: [] }
      }

      const source = /** @type {Record<string, unknown>} */ (parsed)
      const capacity =
        typeof source.capacity === 'number' && Number.isInteger(source.capacity) && source.capacity > 0
          ? source.capacity
          : null

      const rawEntries = Array.isArray(source.entries) ? source.entries : []
      const entries = rawEntries.map((item) => UrlEntry.fromJSON(item)).filter(Boolean)
      return { capacity, entries }
    } catch {
      return { capacity: null, entries: [] }
    }
  }

  /**
   * @param {{capacity: number, entries: UrlEntry[]}} payload
   */
  save(payload) {
    const snapshot = {
      capacity: payload.capacity,
      entries: payload.entries.map((entry) => entry.toJSON()),
    }
    localStorage.setItem(this.storageKey, JSON.stringify(snapshot))
  }
}


export class UrlShortenerService {
  /**
   * @param {UrlRepository} repository
   */
  constructor(repository = new UrlRepository()) {
    this.repository = repository
    this.capacity = null
    /** @type {UrlEntry[]} */
    this.entries = []
    /** @type {Map<string, UrlEntry>} */
    this.shortToEntry = new Map()
    /** @type {Map<string, string>} */
    this.longToShort = new Map()
  }


  load() {
    const loaded = this.repository.load()
    this.capacity = loaded.capacity
    this.entries = loaded.entries
    this.rebuildIndexes()
  }

  /**
   * @returns {number | null}
   */
  getCapacity() {
    return this.capacity
  }

  /**
   * @param {number} capacity
   */
  init(capacity) {
    if (!Number.isInteger(capacity) || capacity <= 0) {
      throw new Error('Capacity must be a positive integer.')
    }

    this.capacity = capacity
    if (this.entries.length > capacity) {
      this.entries = this.entries.slice(0, capacity)
      this.rebuildIndexes()
    }
    this.persist()
  }

  /**
   * @param {string} longUrl
   * @returns {{entry: UrlEntry, isNew: boolean, evicted: UrlEntry | null}}
   */
  shorten(longUrl) {
    if (!this.capacity) {
      throw new Error('Capacity is not initialized.')
    }

    const normalizedLongUrl = this.validateAndNormalizeUrl(longUrl)
    const existingShort = this.longToShort.get(normalizedLongUrl)
    if (existingShort) {
      const existingEntry = this.shortToEntry.get(existingShort)
      if (existingEntry) {
        return { entry: existingEntry, isNew: false, evicted: null }
      }
    }

    let evicted = null
    if (this.entries.length >= this.capacity) {
      evicted = this.evictOne()
    }

    const shortCode = this.generateUniqueShortCode()
    const createdAt = Date.now()
    const entry = new UrlEntry({
      id: `${createdAt}_${Math.random().toString(36).slice(2, 8)}`,
      longUrl: normalizedLongUrl,
      shortCode,
      hitCount: 0,
      createdAt,
    })

    this.entries.push(entry)
    this.shortToEntry.set(shortCode, entry)
    this.longToShort.set(normalizedLongUrl, shortCode)
    this.persist()

    return { entry, isNew: true, evicted }
  }

  /**
   * @param {string} shortCode
   * @returns {UrlEntry}
   */
  resolve(shortCode) {
    const normalizedShortCode = shortCode.trim()
    if (!normalizedShortCode) {
      throw new Error('Short code is required.')
    }

    const entry = this.shortToEntry.get(normalizedShortCode)
    if (!entry) {
      throw new Error('Short URL not found.')
    }

    entry.incrementHits()
    this.persist()
    return entry
  }

  /**
   * @returns {UrlEntry[]}
   */
  listAll() {
    return [...this.entries].sort((a, b) => b.createdAt - a.createdAt)
  }


  persist() {
    if (!this.capacity) {
      return
    }

    this.repository.save({
      capacity: this.capacity,
      entries: this.entries,
    })
  }

  rebuildIndexes() {
    this.shortToEntry.clear()
    this.longToShort.clear()
    for (const entry of this.entries) {
      this.shortToEntry.set(entry.shortCode, entry)
      this.longToShort.set(entry.longUrl, entry.shortCode)
    }
  }

  /**
   * @param {string} input
   * @returns {string}
   */
  validateAndNormalizeUrl(input) {
    const value = input.trim()
    if (!value) {
      throw new Error('Long URL is required.')
    }

    try {
      const parsed = new URL(value)
      if (!['http:', 'https:'].includes(parsed.protocol)) {
        throw new Error('Only http and https protocols are supported.')
      }
      return parsed.toString()
    } catch {
      throw new Error('Invalid URL format.')
    }
  }

  /**
   * @returns {string}
   */
  generateUniqueShortCode() {
    const alphabet = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    const codeLength = 7
    let candidate
    do {
      candidate = ''
      for (let idx = 0; idx < codeLength; idx += 1) {
        candidate += alphabet[Math.floor(Math.random() * alphabet.length)]
      }
    } while (this.shortToEntry.has(candidate))
    return candidate
  }

  /**
   * @returns {UrlEntry}
   */
  evictOne() {
    if (this.entries.length === 0) {
      throw new Error('Cannot evict from empty storage.')
    }

    let evictIndex = 0
    for (let idx = 1; idx < this.entries.length; idx += 1) {
      const candidate = this.entries[idx]
      const selected = this.entries[evictIndex]
      if (candidate.hitCount < selected.hitCount) {
        evictIndex = idx
        continue
      }
      if (candidate.hitCount === selected.hitCount && candidate.createdAt < selected.createdAt) {
        evictIndex = idx
      }
    }

    const [evicted] = this.entries.splice(evictIndex, 1)
    this.shortToEntry.delete(evicted.shortCode)
    this.longToShort.delete(evicted.longUrl)
    return evicted
  }
}
