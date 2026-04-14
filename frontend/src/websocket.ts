export function connectWebSocket(
    onMessage: (data: any) => void
  ) {
  
    const socket = new WebSocket("ws://localhost:8000/ws")
  
    socket.onmessage = (event: MessageEvent) => {
  
      const data = JSON.parse(event.data)
  
      onMessage(data)
  
    }
  
  }