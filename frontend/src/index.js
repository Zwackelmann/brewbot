import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import config from './config.json'
import Home from './Home'
import ListRemotes from './ListRemotes'
import ListPorts from './ListPorts'
import AddRemoteForm from './AddRemoteForm';
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom';

const rootElement = ReactDOM.createRoot(document.getElementById('root'));

rootElement.render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/list-remotes" element={<ListRemotes />} />
        <Route path="/list-ports" element={<ListPorts />} />
        <Route path="/add-remote" element={<AddRemoteForm />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
