const { spawn, exec } = require('child_process');
const path = require('path');
const fs = require('fs');

console.log('🚀 Starting NVIDIA Network Health Check Platform...\n');

// Kill existing processes
function killExistingProcesses() {
  return new Promise((resolve) => {
    console.log('🔄 Cleaning up existing processes...');

    // Kill Python processes
    exec('taskkill /F /IM python.exe /T 2>nul', (error) => {
      if (!error) console.log('  ✓ Stopped Python processes');
    });

    // Kill Node processes (except current)
    exec('taskkill /F /IM node.exe /FI "PID ne ' + process.pid + '" /T 2>nul', (error) => {
      if (!error) console.log('  ✓ Stopped Node processes');
    });

    // Wait a bit for processes to terminate
    setTimeout(resolve, 2000);
  });
}

// Build frontend
function buildFrontend() {
  return new Promise((resolve, reject) => {
    console.log('\n📦 Building frontend...');

    const build = spawn('node', ['build.js'], {
      stdio: 'inherit',
      shell: true
    });

    build.on('close', (code) => {
      if (code === 0) {
        console.log('  ✓ Frontend built successfully\n');
        resolve();
      } else {
        console.error('  ✗ Frontend build failed');
        reject(new Error('Build failed'));
      }
    });
  });
}

// Start backend server
function startBackend() {
  console.log('🐍 Starting backend server...');

  const backend = spawn('python', ['-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000', '--timeout-keep-alive', '300'], {
    cwd: path.join(__dirname, '..', 'backend'),
    stdio: 'inherit',
    shell: true
  });

  backend.on('error', (err) => {
    console.error('  ✗ Backend failed to start:', err.message);
    process.exit(1);
  });

  backend.on('close', (code) => {
    if (code !== 0) {
      console.error(`  ✗ Backend exited with code ${code}`);
      process.exit(code);
    }
  });

  return backend;
}

// Main execution
async function main() {
  try {
    await killExistingProcesses();
    await buildFrontend();

    const backend = startBackend();

    console.log('\n✅ Server started successfully!');
    console.log('📍 Backend: http://localhost:8000');
    console.log('📍 API Docs: http://localhost:8000/docs');
    console.log('\n💡 Press Ctrl+C to stop the server\n');

    // Handle graceful shutdown
    process.on('SIGINT', () => {
      console.log('\n\n🛑 Shutting down server...');
      backend.kill();
      process.exit(0);
    });

    process.on('SIGTERM', () => {
      console.log('\n\n🛑 Shutting down server...');
      backend.kill();
      process.exit(0);
    });

  } catch (error) {
    console.error('\n❌ Failed to start server:', error.message);
    process.exit(1);
  }
}

main();
