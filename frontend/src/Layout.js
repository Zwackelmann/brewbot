import React from 'react';
import { Link } from 'react-router-dom';

function Layout({ children }) {
  return (
    <div>
      <header>
        <h1><Link to="/">Brewbot</Link></h1>
      </header>
      {children}
      <footer>
        <p>|-|</p>
      </footer>
    </div>
  );
}

export default Layout;
