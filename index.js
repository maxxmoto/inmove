const { spawn } = require('child_process');
const path = require('path');

const botScript = path.join(__dirname, 'tg_bot.py');
const python = process.platform === 'win32' ? 'python' : 'python3';

const proc = spawn(python, [botScript], {
  stdio: 'inherit',
  cwd: __dirname,
  env: { ...process.env, PYTHONUNBUFFERED: '1' }
});

proc.on('close', (code) => {
  console.log(`Bot exited with code ${code}`);
  process.exit(code);
});
