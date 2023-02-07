import React, { useState, useEffect } from 'react';
import Layout from './Layout';

class ListRemotes extends React.Component {
  state = {
    remotes: {}
  }

  constructor(props) {
    super(props);
    this.handleShutdown.bind(this);
    this.updateRemotes.bind(this);
  }

  componentDidMount() {
    this.updateRemotes();
  }

  updateRemotes() {
    fetch('/api/list-remotes')
      .then(res => res.json())
      .then(
        (res) => {
          this.setState({ remotes: res.remotes })
        }
      )
  }

  handleShutdown(key) {
    var remote = this.state.remotes[key];
    var path = remote.port + "/" + remote.baudrate;
    fetch("api" + path + "/shutdown")
      .then(res => res.json())
      .then(
        (res) => {
          console.log(res)
        }
      )
      .then(() => this.updateRemotes())

  }

  render() {
    return (
      <Layout>
        <table>
          <thead>
            <tr>
              <th>Port</th>
              <th>Baudrate</th>
              <th>Heartbeat rate</th>
              <th>Input buffer size</th>
              <th>Minimum read sleep</th>
              <th>Input Pins</th>
              <th>Output Pins</th>
              <th>Read interval</th>
              <th>Read serial timeout</th>
              <th>Shutdown</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(this.state.remotes).map(([key, remote]) => {
              const groupedPins = groupPinConfig(remote.pin_config);
              return (
                <tr key={remote.port}>
                  <td>{remote.port}</td>
                  <td>{remote.baudrate}</td>
                  <td>{remote.heartbeat_rate}</td>
                  <td>{remote.in_buf_size}</td>
                  <td>{remote.min_read_sleep}</td>
                  <td>{formatPinConfig(groupedPins.modeIn)}</td>
                  <td>{formatPinConfig(groupedPins.modeOut)}</td>
                  <td>{remote.read_interval}</td>
                  <td>{remote.read_serial_timeout}</td>
                  <td><button onClick={() => this.handleShutdown(key)}>Shutdown</button></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Layout>
    )
  }
}


function formatPinConfig(pinConfig) {
  return Object.entries(pinConfig).map(([key, value]) => `${key} (${value.ad})`).join(", ");
}


function groupPinConfig(pinConfig) {
  return Object.entries(pinConfig).reduce((acc, [ key, value ]) => {
    if (value.mode === 'in') {
      acc.modeIn[key] = value;
    } else if (value.mode === 'out') {
      acc.modeOut[key] = value;
    } else {
      throw new Error(`Invalid value.mode: ${value.mode}`);
    }

    return acc;
  }, { modeIn: {}, modeOut: {}});
}

export default ListRemotes;
