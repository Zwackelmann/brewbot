import React, { useState } from 'react';
import Layout from './Layout';

class AddRemoteForm extends React.Component {
  state = {
    port: '/dev/ttyUSB0',
    baudrate: '115200',
    pins: '2,in,d'
  };

  constructor(props) {
    super(props);
    this.handleSubmit = this.handleSubmit.bind(this);
  }

  handleSubmit() {
    fetch("/api" + this.state.port + "/" + this.state.baudrate + "/new?pins=" + this.state.pins)
      .then(res => res.json())
      .then(
        (res) => {
          console.log(res)
        }
      )
  }

  render() {
    return (
      <Layout>
        <label htmlFor="port">Port:</label>
        <input type="text" id="port" value={this.state.port} onChange={ev => this.setState({ port: ev.target.value })} /><br />
        <label htmlFor="baudrate">Baudrate:</label>
        <input type="text" id="baudrate" value={this.state.baudrate} onChange={ev => this.setState({ baudrate: ev.target.value })} /><br />
        <label htmlFor="pins">Pins:</label>
        <input type="text" id="pins" value={this.state.pins} onChange={ev => this.setState({ pins: ev.target.value })} /><br />
        <button onClick={this.handleSubmit}>Add</button>
      </Layout>
    )
  }
}

export default AddRemoteForm;
