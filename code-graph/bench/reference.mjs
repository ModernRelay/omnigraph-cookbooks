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

const unwrap = (e) => {
  while (e && (ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isSatisfiesExpression(e) ||
    ts.isTypeAssertionExpression(e))) e = e.expression
  return e
}
const isFunctionValue = (e) => !!e && (ts.isArrowFunction(e) || ts.isFunctionExpression(e))
const hasBody = (n) => (ts.isFunctionDeclaration(n) || ts.isMethodDeclaration(n) || ts.isConstructorDeclaration(n) ||
  ts.isGetAccessorDeclaration(n) || ts.isSetAccessorDeclaration(n)) && !!n.body
const isFunction = (n) => hasBody(n) || ts.isArrowFunction(n) || ts.isFunctionExpression(n)
const hasModifier = (n, kind) => (n.modifiers || []).some((m) => m.kind === kind)

// The code the call tracer (instrument.mjs) wraps for one node, to run with
// `owner` as the definition whose code it is. A function's body is entered by a
// call to `callee`, or null for a local function. A derived constructor's body
// is wrapped whole, `super(...)` included: the wrapper is an arrow function,
// which reads `this` only when the code in it does. Before a body runs, a call
// runs the expressions in its parameter list and a construction runs each
// instance field's initializer; each is wrapped with no callee. A function or
// class value is not: making one runs nothing, and wrapping it would lose the
// name it takes from its binding. Destructuring a parameter still reads
// properties before the body, so a getter it reaches is credited to the caller.
export function tracerSites(node, sf, file, owner, callee) {
  const expression = (e) => (isFunctionValue(unwrap(e)) || ts.isClassExpression(unwrap(e)) ? []
    : [{ file, block: false, start: e.getStart(sf), end: e.end, async: false, callee: null, owner, skip: null }])
  if (isFunction(node)) {
    const found = []
    const bindings = (name) => {
      if (ts.isIdentifier(name)) return
      for (const el of name.elements) {
        if (ts.isOmittedExpression(el)) continue
        if (el.propertyName && ts.isComputedPropertyName(el.propertyName)) found.push(el.propertyName.expression)
        if (el.initializer) found.push(el.initializer)
        bindings(el.name)
      }
    }
    for (const p of node.parameters) {
      bindings(p.name)
      if (p.initializer) found.push(p.initializer)
    }
    return [...found.flatMap(expression), {
      file, block: ts.isBlock(node.body), start: node.body.getStart(sf), end: node.body.end,
      async: hasModifier(node, ts.SyntaxKind.AsyncKeyword), callee, owner,
      skip: node.asteriskToken ? 'generator' : null,
    }]
  }
  if (ts.isPropertyDeclaration(node) && node.initializer && !hasModifier(node, ts.SyntaxKind.StaticKeyword)) {
    return expression(node.initializer)
  }
  return []
}

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
  const sites = [] // the code the call tracer wraps (tracerSites)

  const lineOf = (sf, pos) => sf.getLineAndCharacterOfPosition(pos).line + 1
  const nameText = (name) =>
    name && (ts.isIdentifier(name) || ts.isPrivateIdentifier(name) || ts.isStringLiteral(name) ||
      ts.isNumericLiteral(name)) ? name.text : null

  function register(node, id, kind, callable, sf, nameNode, codeNode) {
    const line = lineOf(sf, (nameNode || node).getStart(sf))
    const endLine = lineOf(sf, node.getEnd())
    const known = nodes[id]
    if (!known) {
      nodes[id] = {
        kind, callable, path: rel(sf.fileName), name: id.includes(':') ? id.split(':').pop().split('.').pop() : rel(sf.fileName),
        line, end_line: endLine, digest: null, owns: false,
      }
    } else {
      // Several declarations of one identity, such as an overloaded function's
      // signatures and its implementation, or a getter and its setter, are one
      // definition: it runs from the first to the last, and is callable if any
      // of them is, as the converter decides.
      known.line = Math.min(known.line, line)
      known.end_line = Math.max(known.end_line, endLine)
      known.callable ||= callable
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
    // The code the tracer wraps belongs to the owner its references have.
    sites.push(...tracerSites(node, sf, prefix, nextOwner, fnToId.get(node) ?? null))
    // Function bodies hold locals: their declarations are not global symbols.
    if (isFunction(node)) nextInBody = true
    // A non-function initializer is an expression: walk it as a body, so the
    // declarations in it are locals and its code belongs to the declaration.
    if (!nextInBody && (ts.isVariableDeclaration(node) || ts.isPropertyDeclaration(node)) && node.initializer &&
      !isFunctionValue(unwrap(node.initializer))) {
      visitChildren(node, sf, nextChain, nextOwner, false, node.initializer)
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

  // Dependency injection runs what it is handed: VS Code's
  // `instantiationService.invokeFunction(fn, ...)` calls fn, and
  // `createInstance(C, ...)` constructs a C. Its services are reached this way,
  // so a call or construction through either counts as one.
  function injectedInto(id, method) {
    let e = id
    let p = e.parent
    if (p && ts.isPropertyAccessExpression(p) && p.name === e) { e = p; p = e.parent }
    while (p && (ts.isParenthesizedExpression(p) || ts.isNonNullExpression(p))) { e = p; p = e.parent }
    if (!p || !ts.isCallExpression(p) || p.arguments[0] !== e) return false
    const callee = ts.isPropertyAccessExpression(p.expression) ? p.expression.name : p.expression
    return ts.isIdentifier(callee) && callee.text === method
  }

  function isConstructed(id) {
    let e = id
    let p = e.parent
    if (p && ts.isPropertyAccessExpression(p) && p.name === e) { e = p; p = e.parent }
    return (!!p && ts.isNewExpression(p) && p.expression === e) || injectedInto(id, 'createInstance')
  }

  function isCallee(id) {
    let e = id
    let p = e.parent
    if (p && ts.isPropertyAccessExpression(p) && p.name === e) { e = p; p = e.parent }
    while (p && (ts.isParenthesizedExpression(p) || ts.isNonNullExpression(p))) { e = p; p = e.parent }
    return (!!p && ((ts.isCallExpression(p) && p.expression === e) || (ts.isNewExpression(p) && p.expression === e) ||
      (ts.isTaggedTemplateExpression(p) && p.tag === e))) || injectedInto(id, 'invokeFunction') ||
      injectedInto(id, 'createInstance')
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
    // `new C()` names the class C, and its declared constructor too, to which
    // SCIP resolves the name; the cookbook counts the site as calling both.
    const ctor = isConstructed(id) && (sym.declarations || [])
      .flatMap((d) => (ts.isClassDeclaration(d) ? d.members : []))
      .find((m) => ts.isConstructorDeclaration(m) && declId.get(m))
    for (const d of ctor ? [ctor, ...(sym.declarations || [])] : sym.declarations || []) {
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
