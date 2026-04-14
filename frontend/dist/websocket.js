export function connectWebSocket(onMessage) {
    const socket = new WebSocket("ws://localhost:8000/ws");
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        onMessage(data);
    };
}
