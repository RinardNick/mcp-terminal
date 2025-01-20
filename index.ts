#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import {
  CallToolRequest,
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js'
import { z } from 'zod'
import { spawn } from 'child_process'

// Constants
const DEFAULT_TIMEOUT_MS = 30000 // 30 seconds
const DEFAULT_MAX_OUTPUT = 1024 * 1024 // 1MB

// Define Zod schemas for validation
const CommandArgumentsSchema = z.object({
  command: z.string().min(1, 'Command cannot be empty'),
  allowedCommands: z.array(z.string()).optional(),
  timeoutMs: z.number().min(1).max(300000).optional(), // max 5 minutes
  maxOutputSize: z
    .number()
    .min(1)
    .max(5 * 1024 * 1024)
    .optional(), // max 5MB
})

// Create server instance
const server = new Server(
  {
    name: 'terminal',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
)

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'run_command',
        description: 'Run a terminal command with security controls.',
        inputSchema: {
          type: 'object',
          properties: {
            command: {
              type: 'string',
              description: 'The command to execute',
            },
            allowedCommands: {
              type: 'array',
              items: { type: 'string' },
              description: 'Optional list of allowed command executables',
            },
            timeoutMs: {
              type: 'number',
              description: 'Maximum execution time in milliseconds (default: 30 seconds)',
            },
            maxOutputSize: {
              type: 'number',
              description: 'Maximum output size in bytes (default: 1MB)',
            },
          },
          required: ['command'],
        },
      },
    ],
  }
})

interface CommandResult {
  exitCode: number
  stdout: string
  stderr: string
  startTime: string
  endTime: string
}

// Handle tool execution
server.setRequestHandler(CallToolRequestSchema, async (request: CallToolRequest) => {
  const { name, arguments: args } = request.params

  try {
    if (name === 'run_command') {
      const { command, allowedCommands, timeoutMs, maxOutputSize } =
        CommandArgumentsSchema.parse(args)

      // Validate command if allowedCommands is specified
      if (allowedCommands) {
        // Split command into parts
        const parts = command.split(/\s+/)
        if (!parts.length) {
          throw new Error('Empty command')
        }

        // Check if base command is allowed
        const baseCmd = parts[0]

        // Check for shell operators that could be used for command injection
        const shellOperators = ['&&', '||', '|', ';', '`']
        if (shellOperators.some((op) => command.includes(op))) {
          throw new Error('Shell operators not allowed')
        }

        if (!allowedCommands.includes(baseCmd)) {
          throw new Error(`Command '${baseCmd}' not allowed`)
        }
      }

      const startTime = new Date()
      const result = await new Promise<CommandResult>((resolve, reject) => {
        // Create subprocess
        const process = spawn(command, [], { shell: true })
        let stdout = ''
        let stderr = ''
        let totalSize = 0

        // Handle stdout
        process.stdout.on('data', (data: Buffer) => {
          totalSize += data.length
          if (totalSize > (maxOutputSize || DEFAULT_MAX_OUTPUT)) {
            process.kill()
            reject(new Error(`Output size exceeded ${maxOutputSize || DEFAULT_MAX_OUTPUT} bytes`))
          }
          stdout += data.toString()
        })

        // Handle stderr
        process.stderr.on('data', (data: Buffer) => {
          totalSize += data.length
          if (totalSize > (maxOutputSize || DEFAULT_MAX_OUTPUT)) {
            process.kill()
            reject(new Error(`Output size exceeded ${maxOutputSize || DEFAULT_MAX_OUTPUT} bytes`))
          }
          stderr += data.toString()
        })

        // Handle process completion
        process.on('close', (code: number) => {
          resolve({
            exitCode: code || 0,
            stdout,
            stderr,
            startTime: startTime.toISOString(),
            endTime: new Date().toISOString(),
          })
        })

        // Handle process errors
        process.on('error', (err: Error) => {
          reject(err)
        })

        // Set timeout
        const timeoutId = setTimeout(() => {
          process.kill()
          reject(
            new Error(`Command execution timed out after ${timeoutMs || DEFAULT_TIMEOUT_MS}ms`)
          )
        }, timeoutMs || DEFAULT_TIMEOUT_MS)

        // Clear timeout on process exit
        process.on('exit', () => {
          clearTimeout(timeoutId)
        })
      })

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2),
          },
        ],
      }
    } else {
      throw new Error(`Unknown tool: ${name}`)
    }
  } catch (error: unknown) {
    if (error instanceof z.ZodError) {
      throw new Error(
        `Invalid arguments: ${error.errors
          .map((e: z.ZodError['errors'][number]) => `${e.path.join('.')}: ${e.message}`)
          .join(', ')}`
      )
    }
    throw error
  }
})

// Start the server
async function main() {
  const transport = new StdioServerTransport()
  await server.connect(transport)
  console.error('Terminal MCP Server running on stdio')
}

main().catch((error) => {
  console.error('Fatal error in main():', error)
  process.exit(1)
})
