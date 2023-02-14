import { useState } from 'react'

const RemotesState = () => {
  const [remotes, setRemotes] = useState({})
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
      .then(() => this.syncState())
  }
}

const Foo = () => {
  const x = 1
}

export { RemotesState, Foo }
