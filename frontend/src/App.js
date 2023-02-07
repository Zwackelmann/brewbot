import React from 'react'
import { BrowserRouter, Link, Route, Router } from 'react-router-dom';
import Home from './Home';
import ListRemotes from './ListRemotes';
import AddRemoteForm from './AddRemoteForm';

function App() {
  return (
    <Router>
      <Route exact path="/" component={Home} />
      <Route exact path="/list-remotes" component={ListRemotes} />
      <Route exact path="/list-ports" component={ListPorts} />
      <Route exact path="/add-remote" component={AddRemoteForm} />
    </Router>
  );
}

export default App;
