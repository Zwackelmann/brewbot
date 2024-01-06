import React, { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { fetchRequest, initRequest } from './features/ports/slice';

function App() {
  const dispatch = useDispatch();
  const ports = useSelector((state) => state.ports.ports);
  const loading = useSelector((state) => state.ports.loading);
  const error = useSelector((state) => state.ports.error);

  useEffect(() => {
    dispatch(fetchRequest());
  }, [dispatch]);

  const handleInit = (port) => {
    let req = initRequest(port);
    console.log(req);
    dispatch(req);
  };

  return (
    <div className="App">
      <h1>Ports</h1>
      {loading && <p>Loading...</p>}
      {error && <p>Error: {error}</p>}
      <table>
        <thead>
          <tr>
            <th>Port</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {Object.values(ports).sort().map((port, index) => (
            <tr key={index}>
              <td>{port.name}</td>
              <td>{port.status || 'offline'}</td>
              <td>
                { port.status !== 'connected' && (
                    <button onClick={ () => handleInit(port) }>New</button>
                  )
                }
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;
