/**
 * Import 파서 — Python / JavaScript / TypeScript / package.json
 * 기존 import_parser.py 로직을 TypeScript로 포팅
 */

import { ParsedImport } from './types';

// ─── Python 표준 라이브러리 (필터링 대상) ─────────────────────
const PYTHON_STDLIB = new Set([
  'abc', 'aifc', 'argparse', 'array', 'ast', 'asyncio', 'atexit',
  'base64', 'binascii', 'bisect', 'builtins', 'bz2',
  'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code',
  'codecs', 'codeop', 'collections', 'colorsys', 'compileall',
  'concurrent', 'configparser', 'contextlib', 'contextvars', 'copy',
  'copyreg', 'cProfile', 'crypt', 'csv', 'ctypes', 'curses',
  'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib', 'dis',
  'distutils', 'doctest',
  'email', 'encodings', 'enum', 'errno',
  'faulthandler', 'fcntl', 'filecmp', 'fileinput', 'fnmatch',
  'fractions', 'ftplib', 'functools',
  'gc', 'getopt', 'getpass', 'gettext', 'glob', 'grp', 'gzip',
  'hashlib', 'heapq', 'hmac', 'html', 'http',
  'idlelib', 'imaplib', 'imghdr', 'imp', 'importlib', 'inspect',
  'io', 'ipaddress', 'itertools',
  'json',
  'keyword',
  'lib2to3', 'linecache', 'locale', 'logging', 'lzma',
  'mailbox', 'mailcap', 'marshal', 'math', 'mimetypes', 'mmap',
  'modulefinder', 'multiprocessing',
  'netrc', 'nis', 'nntplib', 'numbers',
  'operator', 'optparse', 'os', 'ossaudiodev',
  'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes', 'pkgutil',
  'platform', 'plistlib', 'poplib', 'posix', 'posixpath', 'pprint',
  'profile', 'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr',
  'pydoc',
  'queue', 'quopri',
  'random', 're', 'readline', 'reprlib', 'resource', 'rlcompleter',
  'runpy',
  'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex',
  'shutil', 'signal', 'site', 'smtpd', 'smtplib', 'sndhdr',
  'socket', 'socketserver', 'sqlite3', 'ssl', 'stat', 'statistics',
  'string', 'stringprep', 'struct', 'subprocess', 'sunau', 'symtable',
  'sys', 'sysconfig', 'syslog',
  'tabnanny', 'tarfile', 'telnetlib', 'tempfile', 'termios', 'test',
  'textwrap', 'threading', 'time', 'timeit', 'tkinter', 'token',
  'tokenize', 'tomllib', 'trace', 'traceback', 'tracemalloc', 'tty',
  'turtle', 'turtledemo', 'types', 'typing',
  'unicodedata', 'unittest', 'urllib', 'uu', 'uuid',
  'venv',
  'warnings', 'wave', 'weakref', 'webbrowser', 'winreg', 'winsound',
  'wsgiref',
  'xdrlib', 'xml', 'xmlrpc',
  'zipapp', 'zipfile', 'zipimport', 'zlib',
  '_thread', '__future__',
]);

// ─── Node.js 빌트인 모듈 (필터링 대상) ──────────────────────
const NODE_BUILTINS = new Set([
  'assert', 'buffer', 'child_process', 'cluster', 'console',
  'constants', 'crypto', 'dgram', 'dns', 'domain', 'events',
  'fs', 'http', 'http2', 'https', 'inspector', 'module', 'net',
  'os', 'path', 'perf_hooks', 'process', 'punycode', 'querystring',
  'readline', 'repl', 'stream', 'string_decoder', 'sys', 'timers',
  'tls', 'trace_events', 'tty', 'url', 'util', 'v8', 'vm',
  'wasi', 'worker_threads', 'zlib',
  'node:fs', 'node:path', 'node:http', 'node:https', 'node:url',
  'node:util', 'node:stream', 'node:crypto', 'node:os',
  'node:child_process', 'node:worker_threads', 'node:events',
  'node:buffer', 'node:assert', 'node:net', 'node:tls',
  'node:dns', 'node:readline', 'node:zlib', 'node:timers',
]);

/** 텍스트의 각 라인에서 import를 추출 */
export function parseImports(text: string, languageId: string): ParsedImport[] {
  switch (languageId) {
    case 'python':
      return parsePython(text);
    case 'javascript':
    case 'typescript':
    case 'javascriptreact':
    case 'typescriptreact':
      return parseJavaScript(text);
    case 'json':
      return parsePackageJson(text);
    default:
      return [];
  }
}

/** Python import 파싱 */
function parsePython(text: string): ParsedImport[] {
  const results: ParsedImport[] = [];
  const lines = text.split('\n');

  // import X, from X import Y
  const importRe = /^\s*import\s+([\w]+)/;
  const fromRe = /^\s*from\s+([\w]+)/;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    let match = importRe.exec(line);
    if (!match) {
      match = fromRe.exec(line);
    }

    if (match) {
      const pkg = match[1];
      if (!PYTHON_STDLIB.has(pkg) && pkg !== '__future__') {
        const startChar = line.indexOf(pkg);
        results.push({
          packageName: pkg,
          line: i,
          startChar,
          endChar: startChar + pkg.length,
        });
      }
    }

    // 동적 import: importlib.import_module("X"), __import__("X")
    const dynamicPatterns = [
      /importlib\.import_module\(\s*['"]([^'"]+)['"]\s*\)/,
      /__import__\(\s*['"]([^'"]+)['"]\s*\)/,
    ];

    for (const pat of dynamicPatterns) {
      const dm = pat.exec(line);
      if (dm) {
        const pkg = dm[1].split('.')[0];
        if (!PYTHON_STDLIB.has(pkg)) {
          const startChar = line.indexOf(dm[1]);
          results.push({
            packageName: pkg,
            line: i,
            startChar,
            endChar: startChar + pkg.length,
          });
        }
      }
    }
  }

  return dedup(results);
}

/** JavaScript/TypeScript import 파싱 */
function parseJavaScript(text: string): ParsedImport[] {
  const results: ParsedImport[] = [];
  const lines = text.split('\n');

  // import ... from 'package'
  const importFromRe = /import\s+.*?from\s+['"]([^'"]+)['"]/;
  // require('package')
  const requireRe = /require\(\s*['"]([^'"]+)['"]\s*\)/;
  // dynamic import('package')
  const dynamicRe = /import\(\s*['"]([^'"]+)['"]\s*\)/;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    for (const re of [importFromRe, requireRe, dynamicRe]) {
      const match = re.exec(line);
      if (match) {
        const raw = match[1];
        // 상대 경로 스킵
        if (raw.startsWith('.') || raw.startsWith('/')) { continue; }

        // 스코프 패키지: @scope/pkg → @scope/pkg
        // 일반: lodash/merge → lodash
        let pkg: string;
        if (raw.startsWith('@')) {
          const parts = raw.split('/');
          pkg = parts.length >= 2 ? `${parts[0]}/${parts[1]}` : raw;
        } else {
          pkg = raw.split('/')[0];
        }

        // node: 접두사 제거
        const cleaned = pkg.replace(/^node:/, '');
        if (!NODE_BUILTINS.has(pkg) && !NODE_BUILTINS.has(cleaned)) {
          const startChar = line.indexOf(raw);
          results.push({
            packageName: pkg,
            line: i,
            startChar: startChar >= 0 ? startChar : 0,
            endChar: (startChar >= 0 ? startChar : 0) + pkg.length,
          });
        }
      }
    }
  }

  return dedup(results);
}

/** package.json 파싱 */
function parsePackageJson(text: string): ParsedImport[] {
  const results: ParsedImport[] = [];

  try {
    const json = JSON.parse(text);
    const depKeys = ['dependencies', 'devDependencies', 'peerDependencies'];
    const lines = text.split('\n');

    for (const key of depKeys) {
      const deps = json[key];
      if (!deps || typeof deps !== 'object') { continue; }

      for (const pkg of Object.keys(deps)) {
        // 해당 패키지가 있는 줄 찾기
        for (let i = 0; i < lines.length; i++) {
          if (lines[i].includes(`"${pkg}"`)) {
            const startChar = lines[i].indexOf(`"${pkg}"`) + 1;
            results.push({
              packageName: pkg,
              line: i,
              startChar,
              endChar: startChar + pkg.length,
            });
            break;
          }
        }
      }
    }
  } catch {
    // JSON 파싱 실패 시 무시
  }

  return results;
}

/** 중복 제거 (같은 패키지명이 여러 줄에 있을 수 있으므로 첫 번째만) */
function dedup(imports: ParsedImport[]): ParsedImport[] {
  const seen = new Set<string>();
  return imports.filter((imp) => {
    const key = `${imp.packageName}`;
    if (seen.has(key)) { return false; }
    seen.add(key);
    return true;
  });
}
