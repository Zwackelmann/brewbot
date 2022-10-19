import React from 'react';
import './App.css';


class ArdRemoteTable extends React.Component {
  constructor(props) {
    super(props);
    this.state = {'remotes': []};
  }

  componentDidMount() {
    fetch('/list-remotes').then(res => res.json()).then(data => {
      this.setState({remotes: data})
      console.log(this.state)
    });
  }

  render() {
    return (
      <table>
        <tbody>
            {this.state.remotes.map((remote, i) => <ArdRemote remote={remote} key={i}/>)}
        </tbody>
      </table>
    );
  }
}


class ArdRemote extends React.Component {
  constructor(props) {
    super(props);
    this.state = {remote: props.remote};
  }

  render() {
    return (
      <tr key="{this.props.key}">
        <td>{this.state.remote.port}</td>
        <td>{this.state.remote.baudrate}</td>
      </tr>
    );
  }
}


function App() {
  return (
    <ArdRemoteTable />
  );
}

export default App;
