import React, { useEffect, useState } from 'react'
import { LedApp } from './ArdApp'
// import { RemotesState } from './RemotesState'

function Foo() {
  const [ports, setPorts] = useState([])
}

const Remotes = () => {
  const remotesState = RemotesState()

  useEffect(() => {
    remotesState.syncState()
  }, []);

  /* const [remotes, setRemotes] = useState({})
  const [ports, setPorts] = useState([])



  const syncState = () => {
    syncRemotes()
    syncPorts()
  }

  const syncRemotes = () => {
    fetch('/api/list-remotes')
      .then(res => res.json())
      .then(
        (res) => {
          setRemotes(res.remotes)
        }
      )
  }

  const syncPorts = () => {
    fetch('/api/list-ports')
      .then(res => res.json())
      .then(
        (res) => {
          setPorts(res.ports)
        }
      )
  }

  const getPorts = () => {
    return ports
  }

  const handleShutdown = (port) => {
    const remote = remotes[port]
    const path = remote.port + "/" + remote.baudrate

    fetch("api" + path + "/shutdown")
      .then(res => res.json())
      .then(
        (res) => {
          // handle res
        }
      )
      .then(() => syncState())
  }

  const handleConnect = (port, app) => {
    const route = "/api" + port + "/" + app.baudrate + "/new"

    var url
    if(app.qstr().length !== 0) {
      url = route + "?" + app.qstr()
    } else {
      url = route
    }

    fetch(url)
      .then(res => res.json())
      .then(
        (res) => {
          console.log(res)
        }
      )
      .then(() => syncState())
  }*/

  return (
    <table>
      <thead>
        <tr>
          <th>Port</th>
          <th>Baudrate</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
      {
        ports.map( port => {
          if(port in remotes) {
            const remote = remotes[port]

            return (
              <tr key={port}>
                <td>{remote.port}</td>
                <td>{remote.baudrate}</td>
                <td><button onClick={() => handleShutdown(port)}>Shutdown</button></td>
              </tr>
            )
          } else {
            return (
              <tr key={port}>
                <td>{port}</td>
                <td></td>
                <td><button onClick={() => handleConnect(port, new LedApp(2))}>Connect</button></td>
              </tr>
            )
          }
        })
      }
      </tbody>
    </table>
  )
}

export default Remotes
