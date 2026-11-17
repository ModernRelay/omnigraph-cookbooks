// Copy a TypeScript checkout and instrument every function under the scope so
// that running its tests records which definition's code called which.
//
//   node instrument.mjs CHECKOUT DEST [--scope src/]
//
// Each function body is wrapped, by inserting text only, in a call to
// `__cg(callee, owner, body)`. `callee` is the definition a call enters, or
// null for a local function; `owner` is the definition that owns the code
// inside, by the same rules as reference.mjs, so a callback written in F
// counts as F's code wherever it runs. The owner travels through awaits in an
// AsyncLocalStorage. At run time each new edge `caller -> callee` is appended
// to a file in CG_TRACE_DIR. Generators, and derived-class constructors whose
// first statement is not `super(...)`, are left as they are.
import fs from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { buildReference } from './reference.mjs'

const require = createRequire(import.meta.url)
const ts = require(process.env.CG_TYPESCRIPT ||
  path.join(path.dirname(fileURLToPath(import.meta.url)), '../sources/indexer/node_modules/typescript'))

const RUNTIME = `const __cg = (globalThis.__cg ??= (() => {
  const { AsyncLocalStorage } = process.getBuiltinModule('node:async_hooks')
  const fs = process.getBuiltinModule('node:fs')
  const als = new AsyncLocalStorage()
  const seen = (process.__cgSeen ??= new Set())
  const dir = process.env.CG_TRACE_DIR
  const file = dir ? dir + '/edges-' + process.pid + '.txt' : null
  return (callee, owner, body) => {
    if (callee !== null) {
      const caller = als.getStore()
      if (caller !== undefined && caller !== '<outside>') {
        const edge = caller + '\\u0000' + callee
        if (!seen.has(edge)) { seen.add(edge); if (file) fs.appendFileSync(file, JSON.stringify(edge) + '\\n') }
      }
    }
    return als.run(owner, body)
  }
})());
`

function outsideFiles(root, scope) {
  const found = []
  const visit = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, e.name)
      const rel = path.relative(root, full).split(path.sep).join('/')
      if (e.isDirectory()) {
        if (!/^(node_modules|\.git|dist|coverage)$/.test(e.name)) visit(full)
      } else if (/\.(m?ts|tsx)$/.test(e.name) && !/\.d\.ts$/.test(e.name)) {
        const isTest = /\.(test|spec)\.tsx?$/.test(e.name)
        if (isTest || (rel.startsWith(scope) && /(^|\/)test-utils\//.test(rel))) found.push(rel)
      }
    }
  }
  for (const top of ['src', 'scripts', 'build']) if (fs.existsSync(path.join(root, top))) visit(path.join(root, top))
  return found
}

function outsideSites(root, file) {
  const text = fs.readFileSync(path.join(root, file), 'utf8')
  const kind = file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, kind)
  const sites = []
  const visit = (node) => {
    const fn = ts.isFunctionDeclaration(node) || ts.isMethodDeclaration(node) || ts.isConstructorDeclaration(node) ||
      ts.isGetAccessorDeclaration(node) || ts.isSetAccessorDeclaration(node) || ts.isArrowFunction(node) ||
      ts.isFunctionExpression(node)
    if (fn && node.body) {
      const derived = ts.isConstructorDeclaration(node) &&
        (node.parent.heritageClauses || []).some((h) => h.token === ts.SyntaxKind.ExtendsKeyword)
      const first = ts.isBlock(node.body) ? node.body.statements[0] : null
      const superFirst = first && ts.isExpressionStatement(first) && ts.isCallExpression(first.expression) &&
        first.expression.expression.kind === ts.SyntaxKind.SuperKeyword
      sites.push({
        file, block: ts.isBlock(node.body), start: node.body.getStart(sf), end: node.body.end,
        async: (node.modifiers || []).some((m) => m.kind === ts.SyntaxKind.AsyncKeyword),
        generator: !!node.asteriskToken, callee: null, owner: '<outside>', after: derived && superFirst ? first.end : null,
        skip: node.asteriskToken ? 'generator' : derived && !superFirst ? 'super not first' : null,
      })
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return sites
}

export function instrument(checkout, dest, { scope = 'src/' } = {}) {
  const src = path.resolve(checkout)
  const out = path.resolve(dest)
  fs.cpSync(src, out, { recursive: true, filter: (p) => !/(^|\/)(node_modules|\.git)(\/|$)/.test(path.relative(src, p)) })
  const { sites } = buildReference(out, { scope })
  const byFile = new Map()
  for (const s of sites) {
    if (!byFile.has(s.file)) byFile.set(s.file, [])
    byFile.get(s.file).push(s)
  }
  // Test files and other code outside the scope run under `<outside>`, so a
  // call their code makes is never credited to the definition that called
  // into them, such as a middleware's `await next()`.
  for (const file of outsideFiles(out, scope)) byFile.set(file, outsideSites(out, file))
  let wrapped = 0
  let skipped = 0
  for (const [file, list] of byFile) {
    const full = path.join(out, file)
    const text = fs.readFileSync(full, 'utf8')
    // Insertions by position. At one position, closing text of inner
    // functions comes first, then opening text of outer ones.
    const at = new Map()
    const add = (pos, kind, depth, str, openPos) => {
      if (!at.has(pos)) at.set(pos, [])
      at.get(pos).push({ kind, depth, str, openPos })
    }
    for (const s of list) {
      if (s.skip) { skipped++; continue }
      const depth = list.filter((o) => o !== s && o.start <= s.start && s.end <= o.end).length
      const head = `__cg(${JSON.stringify(s.callee)}, ${JSON.stringify(s.owner)}, ${s.async ? 'async ' : ''}() => `
      if (s.block) {
        // After `{`, or after a leading `super(...)`, which may have no
        // semicolon of its own: the inserted `;` ends it.
        const open = s.after ?? s.start + 1
        add(open, 'open', depth, `; return ${head}{`)
        add(s.end - 1, 'close', depth, '}); ', open)
      } else {
        add(s.start, 'open', depth, `${head}(`)
        add(s.end, 'close', depth, '))', s.start)
      }
      wrapped++
    }
    const positions = [...at.keys()].sort((a, b) => a - b)
    let result = RUNTIME
    let prev = 0
    for (const pos of positions) {
      result += text.slice(prev, pos)
      const items = at.get(pos)
      // Closes of bodies opened earlier (inner first), then opens (outer
      // first), then closes of bodies opened here, which are empty.
      const closes = items.filter((i) => i.kind === 'close').sort((a, b) => b.depth - a.depth)
      for (const c of closes.filter((i) => i.openPos !== pos)) result += c.str
      for (const o of items.filter((i) => i.kind === 'open').sort((a, b) => a.depth - b.depth)) result += o.str
      for (const c of closes.filter((i) => i.openPos === pos)) result += c.str
      prev = pos
    }
    result += text.slice(prev)
    fs.writeFileSync(full, result)
  }
  return { files: byFile.size, wrapped, skipped }
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname)) {
  const [checkout, dest, ...rest] = process.argv.slice(2)
  const opts = {}
  for (let i = 0; i < rest.length; i += 2) opts[rest[i].replace(/^--/, '')] = rest[i + 1]
  console.log(JSON.stringify(instrument(checkout, dest, opts)))
}
