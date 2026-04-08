import React, { useEffect, useState } from 'react';
import axios from 'axios';

const API = 'http://YOUR_SERVER_IP:8000/admin';

function App() {
  const [commands, setCommands] = useState({});
  const [newName, setNewName] = useState('');
  const [newCode, setNewCode] = useState('');

  const fetchCommands = async () => {
    const res = await axios.get(API + '/commands');
    setCommands(res.data);
  };

  const addCommand = async () => {
    await axios.post(API + '/commands', null, { params: { name: newName, code: newCode } });
    fetchCommands();
    setNewName('');
    setNewCode('');
  };

  const deleteCommand = async (name) => {
    await axios.delete(API + `/commands/${name}`);
    fetchCommands();
  };

  useEffect(() => { fetchCommands(); }, []);

  return (
    <div>
      <h1>AI Assistant Admin Board</h1>
      <div>
        <input placeholder="Command name" value={newName} onChange={e => setNewName(e.target.value)} />
        <textarea placeholder="Python code to execute" value={newCode} onChange={e => setNewCode(e.target.value)} />
        <button onClick={addCommand}>Add / Update</button>
      </div>
      <ul>
        {Object.entries(commands).map(([name, code]) => (
          <li key={name}>
            <b>{name}</b>: {code}
            <button onClick={() => deleteCommand(name)}>Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
export default App;
