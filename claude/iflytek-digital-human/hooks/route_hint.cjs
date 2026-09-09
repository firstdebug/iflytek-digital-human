#!/usr/bin/env node
/** Compatibility wrapper for Claude sessions that cached the old hook command. */
'use strict';

const path = require('path');
const { spawnSync } = require('child_process');

let inputData = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', function(chunk) {
  inputData += chunk;
});
process.stdin.on('end', function() {
  const script = path.join(__dirname, 'route_hint.py');
  const result = spawnSync('python', [script], {
    input: inputData,
    encoding: 'utf8',
    windowsHide: true,
    timeout: 4000,
  });
  if (result.stdout) {
    process.stdout.write(result.stdout);
  }
  process.exit(0);
});
