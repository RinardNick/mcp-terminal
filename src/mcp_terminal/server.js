#!/usr/bin/env node

const { MCPServer } = require('@modelcontextprotocol/server')
const { spawn } = require('child_process')
const yargs = require('yargs/yargs')
const { hideBin } = require('yargs/helpers')

// Parse command line arguments
const argv = yargs(hideBin(process.argv))
  .option('allowed-commands', {
    type: 'string',
    description: 'Comma-separated list of allowed commands',
    default: '',
  })
  .option('timeout-ms', {
    type: 'number',
    description: 'Maximum execution time in milliseconds',
    default: 30000,
  })
  .option('max-memory-mb', {
    type: 'number',
    description: 'Maximum memory usage in megabytes',
  })
  .option('max-processes', {
    type: 'number',
    description: 'Maximum number of processes',
  })
  .option('max-output-size', {
    type: 'number',
    description: 'Maximum output size in bytes',
    default: 1024 * 1024, // 1MB
  })
  .option('log-file', {
    type: 'string',
    description: 'Path to log file for execution logging',
  }).argv

// Convert allowed commands to array
const allowedCommands = argv['allowed-commands']
  ? argv['allowed-commands'].split(',').map((cmd) => cmd.trim())
  : null

// Create MCP server
const server = new MCPServer({
  name: 'terminal',
  version: '1.0.0',
  capabilities: {
    execute: {
      description: 'Execute a terminal command',
      parameters: {
        command: {
          type: 'string',
          description: 'The command to execute',
        },
      },
      returns: {
        type: 'object',
        properties: {
          exitCode: { type: 'number' },
          stdout: { type: 'string' },
          stderr: { type: 'string' },
          startTime: { type: 'string' },
          endTime: { type: 'string' },
        },
      },
    },
  },
})

// Validate command
function validateCommand(command) {
  if (!allowedCommands) return true

  // Split command and get base command
  const parts = command.split(/\s+/)
  if (!parts.length) return false

  const baseCmd = parts[0]

  // Check for shell operators
  const shellOperators = ['&&', '||', '|', ';', '`']
  if (shellOperators.some((op) => command.includes(op))) {
    return false
  }

  return allowedCommands.includes(baseCmd)
}

// Execute command
async function executeCommand(command) {
  // Validate command
  if (!validateCommand(command)) {
    return {
      exitCode: 126,
      stdout: '',
      stderr: 'command not allowed',
      startTime: new Date().toISOString(),
      endTime: new Date().toISOString(),
    }
  }

  return new Promise((resolve, reject) => {
    let stdout = ''
    let stderr = ''
    let killed = false

    const startTime = new Date()

    // Spawn process
    const process = spawn(command, {
      shell: true,
      timeout: argv['timeout-ms'],
    })

    // Track output size
    let totalSize = 0

    // Handle stdout
    process.stdout.on('data', (data) => {
      totalSize += data.length
      if (totalSize > argv['max-output-size']) {
        killed = true
        process.kill()
        reject(new Error(`Output size exceeded ${argv['max-output-size']} bytes`))
        return
      }
      stdout += data

      // Stream output to client
      server.send({
        type: 'output',
        stream: 'stdout',
        data: data.toString(),
      })
    })

    // Handle stderr
    process.stderr.on('data', (data) => {
      totalSize += data.length
      if (totalSize > argv['max-output-size']) {
        killed = true
        process.kill()
        reject(new Error(`Output size exceeded ${argv['max-output-size']} bytes`))
        return
      }
      stderr += data

      // Stream output to client
      server.send({
        type: 'output',
        stream: 'stderr',
        data: data.toString(),
      })
    })

    // Handle completion
    process.on('close', (code) => {
      if (!killed) {
        resolve({
          exitCode: code,
          stdout,
          stderr,
          startTime: startTime.toISOString(),
          endTime: new Date().toISOString(),
        })
      }
    })

    // Handle errors
    process.on('error', (err) => {
      if (err.code === 'ENOENT') {
        resolve({
          exitCode: 127,
          stdout: '',
          stderr: 'command not found',
          startTime: startTime.toISOString(),
          endTime: new Date().toISOString(),
        })
      } else {
        reject(err)
      }
    })
  })
}

// Register command execution handler
server.on('execute', async ({ command }) => {
  try {
    const result = await executeCommand(command)
    return result
  } catch (error) {
    return {
      exitCode: -1,
      stdout: '',
      stderr: error.message,
      startTime: new Date().toISOString(),
      endTime: new Date().toISOString(),
    }
  }
})

// Handle server errors
server.on('error', (error) => {
  console.error('Server error:', error)
  process.exit(1)
})

// Start server
console.log('Starting MCP Terminal server...')
server.start().catch((error) => {
  console.error('Failed to start server:', error)
  process.exit(1)
})
