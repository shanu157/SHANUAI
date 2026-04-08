import React, { useState, useRef } from 'react';

function App() {
  const [result, setResult] = useState('');
  const ws = useRef(null);

  const startListening = () => {
    const recognition = new window.webkitSpeechRecognition();
    recognition.lang = 'en-US';
    recognition.onresult = (event) => {
      const command = event.results[0][0].transcript;
      ws.current.send(command);
    };
    recognition.start();
  };

  const connectWebSocket = () => {
    ws.current = new WebSocket('ws://YOUR_SERVER_IP:8000/ws');
    ws.current.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setResult(data.result);
    };
  };

  return (
    <div>
      <button onClick={connectWebSocket}>Connect</button>
      <button onClick={startListening}>Speak Command</button>
      <p>Result: {result}</p>
    </div>
  );
}
export default App;
