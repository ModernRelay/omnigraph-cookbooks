// A reference symbol and reference graph of a TypeScript checkout, built with
// the TypeScript compiler API directly rather than through SCIP.
//
//   node reference.mjs CHECKOUT OUT.json [--project tsconfig.build.json] [--scope src/]
//
// Nodes are the declarations SCIP names globally: modules, namespaces,
// classes, interfaces, type aliases, enums and their members, top-level
// functions and variables, and the members of object literals assigned to
// them. Identity is `path:Container.member`, with no line numbers, so a node
// keeps its identity while it keeps its name and file. An edge joins the
// innermost declaration that owns code (`owns` on its node) containing an
// identifier to the declaration the type checker resolves it to; `call` marks
// an identifier in callee position.
import crypto from 'node:crypto'
import fs from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)
const ts = require(process.env.CG_TYPESCRIPT || path.join(here, '../sources/indexer/node_modules/typescript'))

export function buildReference(checkout, { project = 'tsconfig.build.json', scope = 'src/' } = {}) {
  const root = path.resolve(checkout)
  const configPath = path.join(root, project)
  const config = ts.readConfigFile(configPath, ts.sys.readFile)
  if (config.error) throw new Error(ts.flattenDiagnosticMessageText(config.error.messageText, '\n'))
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, path.dirname(configPath))
  const rel = (f) => path.relative(root, f).split(path.sep).join('/')
  const inScope = (f) => {
    const r = rel(f)
    return r.startsWith(scope) && !/\.d\.ts$/.test(r) && !/\.test\.tsx?$/.test(r)
  }
  const files = parsed.fileNames.filter(inScope)
  const program = ts.createProgram(files, { ...parsed.options, noEmit: true })
  const checker = program.getTypeChecker()

  // Declarations that own the references inside them, as the converter
  // decides: the ones scip-typescript gives an enclosing range, and the ones
  // the converter reads a range for with the TypeScript parser (constants and
  // variables with an initializer, class fields, getters and setters).
  // Interface members, object-literal members and enum members own nothing.
  const OWNER_KINDS = new Set(['class', 'interface', 'type_alias', 'enum', 'namespace', 'function', 'method',
    'constructor', 'constant', 'variable', 'getter', 'setter', 'property'])
  const ownsCode = (node, kind) => OWNER_KINDS.has(kind) && !ts.isMethodSignature(node) &&
    !ts.isPropertySignature(node) && (!ts.isVariableDeclaration(node) || !!node.initializer) &&
    (!(ts.isGetAccessorDeclaration(node) || ts.isSetAccessorDeclaration(node) || ts.isPropertyDeclaration(node)) ||
      ts.isClassLike(node.parent))
  const nodes = {}
  const declId = new Map() // declaration node -> identity
  const refs = [] // [owner identity, identifier node]
  const keyRefs = [] // [owner identity, object-literal member]
  const fnToId = new Map() // function node -> identity of the definition it is
  const sites = [] // function bodies, for the call tracer

  const lineOf = (sf, pos) => sf.getLineAndCharacterOfPosition(pos).line + 1
  const nameText = (name) =>
    name && (ts.isIdentifier(name) || ts.isPrivateIdentifier(name) || ts.isStringLiteral(name) ||
      ts.isNumericLiteral(name)) ? name.text : null
  const unwrap = (e) => {
    while (e && (ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isSatisfiesExpression(e) ||
      ts.isTypeAssertionExpression(e))) e = e.expression
    return e
  }
  const isFunctionValue = (e) => !!e && (ts.isArrowFunction(e) || ts.isFunctionExpression(e))
  const hasBody = (n) => (ts.isFunctionDeclaration(n) || ts.isMethodDeclaration(n) || ts.isConstructorDeclaration(n) ||
    ts.isGetAccessorDeclaration(n) || ts.isSetAccessorDeclaration(n)) && !!n.body

  function register(node, id, kind, callable, sf, nameNode, codeNode) {
    if (!nodes[id]) {
      nodes[id] = {
        kind, callable, path: rel(sf.fileName), name: id.includes(':') ? id.split(':').pop().split('.').pop() : rel(sf.fileName),
        line: lineOf(sf, (nameNode || node).getStart(sf)), end_line: lineOf(sf, node.getEnd()), digest: null,
        owns: false,
      }
    }
    // A callable's code is its declaration text; overloads and merges add up.
    if (callable && codeNode) {
      const text = codeNode.getText(sf)
      const prev = nodes[id].digest || ''
      nodes[id].digest = crypto.createHash('sha256').update(prev + text).digest('hex').slice(0, 16)
      // The function a call enters, for the tracer: the declaration itself,
      // or the function value a variable or property holds.
      const fn = ts.isVariableDeclaration(codeNode) || ts.isPropertyDeclaration(codeNode)
        ? unwrap(codeNode.initializer) : codeNode
      if (fn) fnToId.set(fn, id)
    }
    declId.set(node, id)
  }

  // Every function with a body, for the call tracer: where its body is, the
  // definition a call to it enters (null for a local function) and the
  // definition that owns the code inside it.
  function recordSite(node, sf, owner) {
    const body = node.body
    if (!body) return
    const isAsync = (node.modifiers || []).some((m) => m.kind === ts.SyntaxKind.AsyncKeyword)
    const site = {
      file: rel(sf.fileName), block: ts.isBlock(body), start: body.getStart(sf), end: body.end,
      async: isAsync, generator: !!node.asteriskToken, callee: fnToId.get(node) ?? null, owner,
      constructor: ts.isConstructorDeclaration(node), after: null, skip: null,
    }
    if (site.generator) site.skip = 'generator'
    if (site.constructor) {
      const cls = node.parent
      const derived = (cls.heritageClauses || []).some((h) => h.token === ts.SyntaxKind.ExtendsKeyword)
      const first = body.statements[0]
      const superFirst = first && ts.isExpressionStatement(first) && ts.isCallExpression(first.expression) &&
        first.expression.expression.kind === ts.SyntaxKind.SuperKeyword
      if (derived && !superFirst) site.skip = 'super not first'
      else if (derived) site.after = first.end
    }
    sites.push(site)
  }

  // Walk one file. `chain` is the container names above this point, `owner`
  // the identity that owns references here, `inBody` true inside a function
  // body, where declarations are locals and belong to their owner.
  function walk(node, sf, chain, owner, inBody) {
    const prefix = rel(sf.fileName)
    const idOf = (names) => `${prefix}:${names.join('.')}`
    let nextChain = chain
    let nextOwner = owner
    let nextInBody = inBody
    if (!inBody) {
      let name = null
      let kind = null
      let callable = false
      let codeNode = null
      if (ts.isFunctionDeclaration(node) && node.name) {
        name = node.name.text; kind = 'function'; callable = !!node.body; codeNode = node.body ? node : null
      } else if (ts.isClassDeclaration(node) && node.name) {
        name = node.name.text; kind = 'class'
      } else if (ts.isInterfaceDeclaration(node)) {
        name = node.name.text; kind = 'interface'
      } else if (ts.isTypeAliasDeclaration(node)) {
        name = node.name.text; kind = 'type_alias'
      } else if (ts.isEnumDeclaration(node)) {
        name = node.name.text; kind = 'enum'
      } else if (ts.isEnumMember(node)) {
        name = nameText(node.name); kind = 'enum_member'
      } else if (ts.isModuleDeclaration(node) && ts.isIdentifier(node.name)) {
        name = node.name.text; kind = 'namespace'
      } else if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
        const init = unwrap(node.initializer)
        name = node.name.text
        callable = isFunctionValue(init)
        kind = (node.parent.flags & ts.NodeFlags.Const) ? 'constant' : 'variable'
        codeNode = callable ? node : null
      } else if (ts.isConstructorDeclaration(node)) {
        name = 'constructor'; kind = 'constructor'; callable = !!node.body; codeNode = node.body ? node : null
      } else if (ts.isMethodDeclaration(node) || ts.isMethodSignature(node)) {
        name = nameText(node.name); kind = 'method'; callable = true; codeNode = hasBody(node) ? node : null
      } else if (ts.isGetAccessorDeclaration(node) || ts.isSetAccessorDeclaration(node)) {
        name = nameText(node.name); kind = ts.isGetAccessorDeclaration(node) ? 'getter' : 'setter'
        callable = true; codeNode = node.body ? node : null
      } else if (ts.isPropertyDeclaration(node) || ts.isPropertySignature(node)) {
        // Class fields and interface or type-literal properties. Object-literal
        // members are not symbols: SCIP gives them no global name either.
        name = nameText(node.name); kind = 'property'
        const init = unwrap(node.initializer)
        callable = isFunctionValue(init) || (!!node.type && ts.isFunctionTypeNode(node.type))
        codeNode = isFunctionValue(init) ? node : null
      }
      if (name) {
        const id = idOf([...chain, name])
        register(node, id, kind, callable, sf, node.name, codeNode)
        nextChain = [...chain, name]
        // References belong to the innermost definition that owns code;
        // members that own none belong to their container. Methods own their
        // references with or without a body (abstract methods, overload
        // signatures); interface method signatures do not.
        if (ownsCode(node, kind)) {
          nextOwner = id
          nodes[id].owns = true
        }
      }
    }
    // Function bodies hold locals: their declarations are not global symbols.
    if (hasBody(node) || ts.isArrowFunction(node) || ts.isFunctionExpression(node)) {
      recordSite(node, sf, nextOwner)
      nextInBody = true
    }
    // A non-function initializer is an expression: walk it as a body, so the
    // declarations in it are locals and its code belongs to the declaration.
    if (!nextInBody && (ts.isVariableDeclaration(node) || ts.isPropertyDeclaration(node)) && node.initializer &&
      !isFunctionValue(unwrap(node.initializer))) {
      visitChildren(node, sf, nextChain, nextOwner, true, node.initializer)
      return
    }
    if (isReference(node)) refs.push([nextOwner, node])
    // An object-literal key names the property of the object's contextual
    // type it fills, `{ unmount }` in a `Root` naming `Root.unmount`.
    if ((ts.isPropertyAssignment(node) || ts.isShorthandPropertyAssignment(node) || ts.isMethodDeclaration(node)) &&
      node.parent && ts.isObjectLiteralExpression(node.parent) && node.name) {
      keyRefs.push([nextOwner, node])
    }
    visitChildren(node, sf, nextChain, nextOwner, nextInBody)
  }

  // An identifier that names something, an import or export specifier, or a
  // module path string in an import, export or import type.
  function isReference(node) {
    if (ts.isStringLiteral(node)) {
      const p = node.parent
      return !!p && (((ts.isImportDeclaration(p) || ts.isExportDeclaration(p)) && p.moduleSpecifier === node) ||
        (ts.isLiteralTypeNode(p) && p.parent && ts.isImportTypeNode(p.parent)))
    }
    if (!(ts.isIdentifier(node) || ts.isPrivateIdentifier(node))) return false
    const p = node.parent
    if (p && (ts.isImportSpecifier(p) || ts.isExportSpecifier(p))) return (p.propertyName || p.name) === node
    if (p && ts.isImportClause(p)) return true
    return !isDeclarationName(node)
  }

  function visitChildren(node, sf, chain, owner, inBody, expressionChild) {
    ts.forEachChild(node, (child) => {
      // An expression-valued initializer is walked as a body; the rest of the
      // declaration (its name and type) is not.
      walk(child, sf, chain, owner, inBody || child === expressionChild)
    })
  }

  // The name a declaration introduces. getNameOfDeclaration alone is not
  // enough: it also returns the name of a property access (`a.b`), which
  // declares a property only in JavaScript files and is a reference here.
  const DECLARATION_KINDS = new Set([
    ts.SyntaxKind.VariableDeclaration, ts.SyntaxKind.FunctionDeclaration, ts.SyntaxKind.ClassDeclaration,
    ts.SyntaxKind.ClassExpression, ts.SyntaxKind.FunctionExpression, ts.SyntaxKind.InterfaceDeclaration,
    ts.SyntaxKind.TypeAliasDeclaration, ts.SyntaxKind.EnumDeclaration, ts.SyntaxKind.EnumMember,
    ts.SyntaxKind.ModuleDeclaration, ts.SyntaxKind.Parameter, ts.SyntaxKind.PropertyDeclaration,
    ts.SyntaxKind.PropertySignature, ts.SyntaxKind.MethodDeclaration, ts.SyntaxKind.MethodSignature,
    ts.SyntaxKind.GetAccessor, ts.SyntaxKind.SetAccessor, ts.SyntaxKind.PropertyAssignment,
    ts.SyntaxKind.BindingElement, ts.SyntaxKind.TypeParameter, ts.SyntaxKind.NamespaceImport,
    ts.SyntaxKind.ImportEqualsDeclaration, ts.SyntaxKind.NamespaceExport,
  ])
  function isDeclarationName(id) {
    const p = id.parent
    if (!p || !DECLARATION_KINDS.has(p.kind)) return false
    // In `{ a: b }` a binding element's propertyName names the source property.
    if (ts.isBindingElement(p) && p.propertyName === id) return false
    return p.name === id
  }

  for (const f of files) {
    const sf = program.getSourceFile(f)
    const moduleId = rel(sf.fileName)
    nodes[moduleId] = { kind: 'module', callable: false, path: moduleId, name: path.basename(moduleId), line: 1,
      end_line: lineOf(sf, sf.getEnd()), digest: null, owns: true }
    declId.set(sf, moduleId)
    ts.forEachChild(sf, (child) => walk(child, sf, [], moduleId, false))
  }

  function isConstructed(id) {
    let e = id
    let p = e.parent
    if (p && ts.isPropertyAccessExpression(p) && p.name === e) { e = p; p = e.parent }
    return !!p && ts.isNewExpression(p) && p.expression === e
  }

  function isCallee(id) {
    let e = id
    let p = e.parent
    if (p && ts.isPropertyAccessExpression(p) && p.name === e) { e = p; p = e.parent }
    while (p && (ts.isParenthesizedExpression(p) || ts.isNonNullExpression(p))) { e = p; p = e.parent }
    return !!p && ((ts.isCallExpression(p) && p.expression === e) || (ts.isNewExpression(p) && p.expression === e) ||
      (ts.isTaggedTemplateExpression(p) && p.tag === e))
  }

  const edges = {}
  for (const [owner, id] of refs) {
    let sym
    if (ts.isShorthandPropertyAssignment(id.parent) && id.parent.name === id) {
      sym = checker.getShorthandAssignmentValueSymbol(id.parent)
    } else if (ts.isExportSpecifier(id.parent) && !id.parent.parent.parent.moduleSpecifier) {
      sym = checker.getExportSpecifierLocalTargetSymbol(id.parent)
    } else {
      sym = checker.getSymbolAtLocation(id)
    }
    if (!sym) continue
    if (sym.flags & ts.SymbolFlags.Alias) {
      try { sym = checker.getAliasedSymbol(sym) } catch { continue }
    }
    const targets = new Set()
    // `new C()` names C's declared constructor, as SCIP records it; a class
    // without one is named itself.
    const ctor = isConstructed(id) && (sym.declarations || [])
      .flatMap((d) => (ts.isClassDeclaration(d) ? d.members : []))
      .find((m) => ts.isConstructorDeclaration(m) && declId.get(m))
    for (const d of ctor ? [ctor] : sym.declarations || []) {
      const t = declId.get(d)
      if (t) targets.add(t)
    }
    addEdges(owner, targets, isCallee(id))
  }
  for (const [owner, member] of keyRefs) {
    const name = nameText(member.name)
    const type = name && checker.getContextualType(member.parent)
    if (!type) continue
    const targets = new Set()
    for (const t of type.isUnion() ? type.types : [type]) {
      const prop = t.getProperty(name)
      for (const d of prop?.declarations || []) if (declId.get(d)) targets.add(declId.get(d))
    }
    addEdges(owner, targets, false)
  }
  // A class member implements or overrides each member of the same name that
  // its class's heritage types declare, inherited members included: the
  // bodies a call through the interface or base member can run.
  const implementsEdges = []
  for (const [decl, id] of declId) {
    if (!ts.isClassDeclaration(decl) || !decl.heritageClauses) continue
    const bases = decl.heritageClauses.flatMap((h) => h.types).map((t) => checker.getTypeAtLocation(t))
    for (const member of decl.members) {
      const memberId = declId.get(member)
      const name = member.name && nameText(member.name)
      if (!memberId || !name) continue
      const targets = new Set()
      for (const base of bases) {
        const prop = base.getProperty(name)
        for (const d of prop?.declarations || []) {
          const t = declId.get(d)
          if (t && t !== memberId) targets.add(t)
        }
      }
      for (const t of targets) implementsEdges.push([memberId, t])
    }
  }
  return { nodes, edges, sites, implements: implementsEdges.sort() }

  function addEdges(owner, targets, call) {
    for (const t of targets) {
      const key = `${owner}\u0000${t}`
      const e = edges[key] || (edges[key] = { call: false, sites: 0 })
      e.call = e.call || call
      e.sites += 1
    }
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const [checkout, out, ...rest] = process.argv.slice(2)
  const opts = {}
  for (let i = 0; i < rest.length; i += 2) opts[rest[i].replace(/^--/, '')] = rest[i + 1]
  const { sites, ...ref } = buildReference(checkout, opts)
  fs.writeFileSync(out, JSON.stringify(ref))
  const calls = Object.values(ref.edges).filter((e) => e.call).length
  console.log(`${Object.keys(ref.nodes).length} nodes, ${Object.keys(ref.edges).length} edges, ${calls} with a call`)
}
