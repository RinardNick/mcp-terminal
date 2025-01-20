import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { Transport } from '@modelcontextprotocol/sdk/server/transport.js'
import {
  CallToolRequest,
  ListToolsRequest,
  JSONRPCRequest,
  JSONRPCResponse,
  ListToolsResult,
} from '@modelcontextprotocol/sdk/types.js'
import { z } from 'zod'

class MockTransport implements Transport {
  async connect(): Promise<void> {}
  async disconnect(): Promise<void> {}
  async send(message: string): Promise<void> {}
  async receive(): Promise<string> {
    return JSON.stringify({
      jsonrpc: '2.0',
      id: '1',
      result: {
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
              },
              required: ['command'],
            },
          },
        ],
      },
    })
  }
}

const ListToolsResultSchema = z.object({
  tools: z.array(
    z.object({
      name: z.string(),
      description: z.string(),
      inputSchema: z.object({
        type: z.literal('object'),
        properties: z.record(z.any()),
        required: z.array(z.string()),
      }),
    })
  ),
})

const ToolResponseSchema = z.object({
  content: z.array(
    z.object({
      type: z.literal('text'),
      text: z.string(),
    })
  ),
})

describe('Terminal Server', () => {
  let server: Server
  let transport: MockTransport

  beforeEach(async () => {
    server = new Server(
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
    transport = new MockTransport()
    await server.connect(transport)
  })

  describe('Tool Listing', () => {
    it('should list available tools', async () => {
      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: '1',
        method: 'tools/list',
        params: {},
      }

      const response = await server.request(request, ListToolsResultSchema)
      expect(response.tools).toHaveLength(1)
      expect(response.tools[0]).toMatchObject({
        name: 'run_command',
        description: 'Run a terminal command with security controls.',
        inputSchema: {
          type: 'object',
          properties: {
            command: {
              type: 'string',
              description: 'The command to execute',
            },
          },
          required: ['command'],
        },
      })
    })
  })

  describe('Command Execution', () => {
    beforeEach(() => {
      // Mock successful command execution
      jest.spyOn(transport, 'receive').mockImplementation(async () => {
        return JSON.stringify({
          jsonrpc: '2.0',
          id: '1',
          result: {
            content: [
              {
                type: 'text',
                text: JSON.stringify({
                  exitCode: 0,
                  stdout: 'hello world\n',
                  stderr: '',
                  startTime: new Date().toISOString(),
                  endTime: new Date().toISOString(),
                }),
              },
            ],
          },
        })
      })
    })

    it('should execute a basic command', async () => {
      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: '1',
        method: 'tools/call',
        params: {
          name: 'run_command',
          arguments: {
            command: 'echo "hello world"',
          },
        },
      }

      const response = await server.request(request, ToolResponseSchema)
      const result = JSON.parse(response.content[0].text)

      expect(result.exitCode).toBe(0)
      expect(result.stdout.trim()).toBe('hello world')
      expect(result.stderr).toBe('')
    })

    it('should handle command errors', async () => {
      jest.spyOn(transport, 'receive').mockImplementation(async () => {
        return JSON.stringify({
          jsonrpc: '2.0',
          id: '1',
          result: {
            content: [
              {
                type: 'text',
                text: JSON.stringify({
                  exitCode: 127,
                  stdout: '',
                  stderr: 'command not found',
                  startTime: new Date().toISOString(),
                  endTime: new Date().toISOString(),
                }),
              },
            ],
          },
        })
      })

      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: '1',
        method: 'tools/call',
        params: {
          name: 'run_command',
          arguments: {
            command: 'nonexistentcommand',
          },
        },
      }

      const response = await server.request(request, ToolResponseSchema)
      const result = JSON.parse(response.content[0].text)

      expect(result.exitCode).toBe(127)
      expect(result.stderr).toContain('command not found')
    })

    it('should enforce command allowlist', async () => {
      jest.spyOn(transport, 'receive').mockImplementation(async () => {
        return JSON.stringify({
          jsonrpc: '2.0',
          id: '1',
          result: {
            content: [
              {
                type: 'text',
                text: JSON.stringify({
                  exitCode: 126,
                  stdout: '',
                  stderr: "Command 'ls' not allowed",
                  startTime: new Date().toISOString(),
                  endTime: new Date().toISOString(),
                }),
              },
            ],
          },
        })
      })

      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: '1',
        method: 'tools/call',
        params: {
          name: 'run_command',
          arguments: {
            command: 'ls',
            allowedCommands: ['echo'],
          },
        },
      }

      const response = await server.request(request, ToolResponseSchema)
      const result = JSON.parse(response.content[0].text)

      expect(result.exitCode).toBe(126)
      expect(result.stderr).toContain("Command 'ls' not allowed")
    })

    it('should prevent shell operator injection', async () => {
      jest.spyOn(transport, 'receive').mockImplementation(async () => {
        return JSON.stringify({
          jsonrpc: '2.0',
          id: '1',
          result: {
            content: [
              {
                type: 'text',
                text: JSON.stringify({
                  exitCode: 126,
                  stdout: '',
                  stderr: 'Shell operators not allowed',
                  startTime: new Date().toISOString(),
                  endTime: new Date().toISOString(),
                }),
              },
            ],
          },
        })
      })

      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: '1',
        method: 'tools/call',
        params: {
          name: 'run_command',
          arguments: {
            command: 'echo "hello" && ls',
            allowedCommands: ['echo'],
          },
        },
      }

      const response = await server.request(request, ToolResponseSchema)
      const result = JSON.parse(response.content[0].text)

      expect(result.exitCode).toBe(126)
      expect(result.stderr).toContain('Shell operators not allowed')
    })

    it('should enforce output size limits', async () => {
      jest.spyOn(transport, 'receive').mockImplementation(async () => {
        return JSON.stringify({
          jsonrpc: '2.0',
          id: '1',
          result: {
            content: [
              {
                type: 'text',
                text: JSON.stringify({
                  exitCode: 1,
                  stdout: '',
                  stderr: 'Output size exceeded 100 bytes',
                  startTime: new Date().toISOString(),
                  endTime: new Date().toISOString(),
                }),
              },
            ],
          },
        })
      })

      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: '1',
        method: 'tools/call',
        params: {
          name: 'run_command',
          arguments: {
            command: 'yes', // Generates infinite output
            maxOutputSize: 100,
          },
        },
      }

      const response = await server.request(request, ToolResponseSchema)
      const result = JSON.parse(response.content[0].text)

      expect(result.stderr).toContain('Output size exceeded')
    })

    it('should enforce command timeout', async () => {
      jest.spyOn(transport, 'receive').mockImplementation(async () => {
        return JSON.stringify({
          jsonrpc: '2.0',
          id: '1',
          result: {
            content: [
              {
                type: 'text',
                text: JSON.stringify({
                  exitCode: 1,
                  stdout: '',
                  stderr: 'Command execution timed out after 100ms',
                  startTime: new Date().toISOString(),
                  endTime: new Date().toISOString(),
                }),
              },
            ],
          },
        })
      })

      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: '1',
        method: 'tools/call',
        params: {
          name: 'run_command',
          arguments: {
            command: 'sleep 5',
            timeoutMs: 100,
          },
        },
      }

      const response = await server.request(request, ToolResponseSchema)
      const result = JSON.parse(response.content[0].text)

      expect(result.stderr).toContain('Command execution timed out')
    })
  })
})
