import React, { useState, useEffect } from 'react';
import Layout from './Layout';

function ListRemotes() {
  const [ports, setPorts] = useState([])

  // Fetch the data from the API in the componentDidMount lifecycle hook
  useEffect(() => {
    async function fetchData() {
      const response = await fetch('/api/list-ports')
      const data = await response.json()
      setPorts(data.ports)
    }
    fetchData()
  }, [])

  return (
    <Layout>
      <table>
        <thead>
          <tr>
            <th>Port</th>
          </tr>
        </thead>
        <tbody>
          {ports.map(port =>
            (
              <tr key={port}>
                <td>{port}</td>
              </tr>
            )
          )}
        </tbody>
      </table>
    </Layout>
  )
}

export default ListRemotes;
