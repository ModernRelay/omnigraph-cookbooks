// The definitions scip-typescript gives no enclosing range, with the range they
// would have, so build_seed.py can give the references inside them an owner.
//
// scip-typescript 0.6.2 sets an enclosing range only on functions, classes,
// interfaces, enums, type aliases, methods, constructors and constants whose
// initializer is a function. A constant holding a table of functions, a class
// field and a getter or setter get none, so the references inside them would
// otherwise belong to the module or class around them.
//
// Reads {"root": checkout, "files": [paths relative to it]} on stdin and writes
// {path: [[name line, name character, start line, start character, end line,
// end character, initializer is a function], ...]} on stdout, 0-based like SCIP.
// The name position is where the indexer puts the definition's occurrence; the
// range follows the indexer's own rule for function constants: the whole
// statement when it declares one name, else the declaration.
//
//     echo '{"root": ".", "files": ["src/a.ts"]}' | node code-graph/sources/indexer/extents.mjs

import { createRequire } from 'node:module'
import fs from 'node:fs'
import path from 'node:path'

const ts = createRequire(import.meta.url)('typescript')

function unwrap(expression) {
  let e = expression
  while (e && (ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isSatisfiesExpression(e) ||
               ts.isTypeAssertionExpression(e) || ts.isNonNullExpression(e))) {
    e = e.expression
  }
  return e
}

function extents(sourceFile) {
  const out = []
  const push = (name, node, initializer) => {
    const at = (pos) => sourceFile.getLineAndCharacterOfPosition(pos)
    const n = at(name.getStart(sourceFile))
    const s = at(node.getStart(sourceFile))
    const e = at(node.getEnd())
    const init = unwrap(initializer)
    out.push([n.line, n.character, s.line, s.character, e.line, e.character, Boolean(init && ts.isFunctionLike(init))])
  }
  const visit = (node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      const statement = node.parent.parent
      const whole = ts.isVariableStatement(statement) && statement.declarationList.declarations.length === 1
      push(node.name, whole ? statement : node, node.initializer)
    } else if ((ts.isPropertyDeclaration(node) || ts.isGetAccessorDeclaration(node) || ts.isSetAccessorDeclaration(node)) &&
               ts.isClassLike(node.parent) && (ts.isIdentifier(node.name) || ts.isPrivateIdentifier(node.name))) {
      push(node.name, node, ts.isPropertyDeclaration(node) ? node.initializer : undefined)
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return out
}

const request = JSON.parse(fs.readFileSync(0, 'utf8'))
const result = {}
for (const file of request.files) {
  const text = fs.readFileSync(path.join(request.root, file), 'utf8')
  const kind = file.endsWith('.tsx') ? ts.ScriptKind.TSX : file.endsWith('.jsx') ? ts.ScriptKind.JSX
    : /\.[cm]?js$/.test(file) ? ts.ScriptKind.JS : ts.ScriptKind.TS
  result[file] = extents(ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, kind))
}
process.stdout.write(JSON.stringify(result))
