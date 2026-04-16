export interface ParsedParagraphLocation {
  /** Display text shown in the clickable link */
  linktext: string;
  doc_id: string;
  page: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  /**
   * Data-origin label written by the backend:
   *   undefined / 'text' – regular document text  → rendered blue
   *   'table'            – value from a table cell → rendered yellow
   *   'llm'              – LLM-computed value      → reserved for future use
   */
  source?: string;
}

/**
 * Matches NEW format tags (linktext field present, source field optional):
 *   {paragraph_location: linktext="TEXT", [source=SOURCE,] doc_id=X, page=N, ...}
 *
 * The preceding TEXT in the document is removed by preprocessParagraphLoc()
 * before this regex is applied, so we only need to match the tag itself.
 */
export const PARAGRAPH_LOC_RE =
  /(\{paragraph_location:\s*linktext="[^"]+",\s*(?:source=\w+,\s*)?doc_id=[^,}]+,\s*page=\d+,\s*x0=[\d.]+,\s*y0=[\d.]+,\s*x1=[\d.]+,\s*y1=[\d.]+\})/g;

/**
 * Matches LEGACY format (no linktext field):
 *   NUMBER{paragraph_location: doc_id=X, page=N, x0=X0, y0=Y0, x1=X1, y1=Y1}
 * NUMBER must start with a digit to avoid capturing preceding Chinese text.
 */
export const PARAGRAPH_LOC_LEGACY_RE =
  /(\d[\d,.%‰°℃℉+\-]*\{paragraph_location:\s*doc_id=[^,}]+,\s*page=\d+,\s*x0=[\d.]+,\s*y0=[\d.]+,\s*x1=[\d.]+,\s*y1=[\d.]+\})/g;

const NEW_FIELDS_RE =
  /^\{paragraph_location:\s*linktext="([^"]+)",\s*(?:source=(\w+),\s*)?doc_id=([^,}]+),\s*page=(\d+),\s*x0=([\d.]+),\s*y0=([\d.]+),\s*x1=([\d.]+),\s*y1=([\d.]+)\}$/;

const LEGACY_FIELDS_RE =
  /^(.+?)\{paragraph_location:\s*doc_id=([^,}]+),\s*page=(\d+),\s*x0=([\d.]+),\s*y0=([\d.]+),\s*x1=([\d.]+),\s*y1=([\d.]+)\}$/;

/**
 * Pre-process text so that reactStringReplace can work with a simple tag regex.
 *
 * For NEW-format tags: the linktext value immediately precedes the tag in the
 * source text (e.g. "2024年1 月{paragraph_location: linktext="2024年1 月",...}").
 * This function removes the duplicate preceding text, leaving only the tag:
 *   "{paragraph_location: linktext="2024年1 月",...}"
 *
 * Legacy-format text (no linktext field) is left unchanged.
 */
export function preprocessParagraphLoc(text: string): string {
  const TAG_RE = /\{paragraph_location:\s*linktext="([^"]+)",[^}]+\}/g;
  let result = '';
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = TAG_RE.exec(text)) !== null) {
    const linktext = match[1];
    const tagStart = match.index;
    const textBefore = text.slice(lastIndex, tagStart);

    // Build a flexible regex: spaces in linktext become \s* so that cases where
    // the LLM collapses or adds spaces (e.g. "2024年2月" vs "2024年2 月") still
    // match and the duplicate preceding text is correctly stripped.
    const flexPattern = linktext
      .replace(/[.*+?^${}()|[\]\\]/g, '\\$&') // escape regex special chars
      .replace(/\s+/g, '\\s*'); // spaces → optional whitespace

    // Pass 1: strip bare linktext at end of textBefore.
    //   e.g. "根据《表名》表名" → "根据《表名》"
    let stripped = textBefore;
    const bareRE = new RegExp(flexPattern + '$');
    const m2 = bareRE.exec(stripped);
    if (m2 !== null) {
      stripped = stripped.slice(0, m2.index);
    }

    // Pass 2: strip 《linktext》 / "linktext" / 「linktext」 at end of what remains.
    // Handles cases where the LLM wraps the name in book-title marks before
    // also copying the annotated form, e.g.:
    //   "根据《2024年1月...统计表》2024年1月...统计表{paragraph_location:...}"
    // After pass 1 we have "根据《2024年1月...统计表》" — pass 2 removes the 《》 copy.
    const quotedRE = new RegExp(
      '[《"「\'"]\\s*' + flexPattern + '\\s*[》"」\'"]$',
    );
    const m3 = quotedRE.exec(stripped);
    if (m3 !== null) {
      stripped = stripped.slice(0, m3.index);
    }

    result += stripped;
    result += match[0]; // keep the tag
    lastIndex = tagStart + match[0].length;
  }
  result += text.slice(lastIndex);
  return result;
}

/**
 * Parse a matched string into structured fields.
 * Handles both new format (with linktext) and legacy format (number prefix).
 * Returns null if the string does not match either format.
 */
export function parseParagraphLocation(
  matched: string,
): ParsedParagraphLocation | null {
  // Try new format first
  // Groups: 1=linktext, 2=source(optional), 3=doc_id, 4=page, 5=x0, 6=y0, 7=x1, 8=y1
  let m = NEW_FIELDS_RE.exec(matched);
  if (m) {
    return {
      linktext: m[1].trim(),
      source: m[2] ?? undefined,
      doc_id: m[3].trim(),
      page: parseInt(m[4], 10),
      x0: parseFloat(m[5]),
      y0: parseFloat(m[6]),
      x1: parseFloat(m[7]),
      y1: parseFloat(m[8]),
    };
  }
  // Try legacy format (NUMBER{paragraph_location: doc_id=...})
  m = LEGACY_FIELDS_RE.exec(matched);
  if (m) {
    return {
      linktext: m[1].trim(),
      doc_id: m[2].trim(),
      page: parseInt(m[3], 10),
      x0: parseFloat(m[4]),
      y0: parseFloat(m[5]),
      x1: parseFloat(m[6]),
      y1: parseFloat(m[7]),
    };
  }
  return null;
}
