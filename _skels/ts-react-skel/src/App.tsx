import { useState } from 'react';
import './App.css';

interface ProjectInfo {
  project: string;
  version: string;
  framework: string;
  status: string;
}

const projectInfo: ProjectInfo = {
  project: 'ts-react-skel',
  version: '1.0.0',
  framework: 'React + Vite + TypeScript',
  status: 'running',
};

function App() {
  const [count, setCount] = useState(0);

  return (
    <div className="app">
      <header className="app-header">
        <h1>{projectInfo.project}</h1>
        <p>v{projectInfo.version}</p>
      </header>
      <main>
        <div className="card">
          <button onClick={() => setCount((c) => c + 1)}>Count: {count}</button>
        </div>
        <div className="info">
          <p>Framework: {projectInfo.framework}</p>
          <p>Status: {projectInfo.status}</p>
        </div>
      </main>
    </div>
  );
}

export default App;
