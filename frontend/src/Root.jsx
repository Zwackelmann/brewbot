import React from 'react';
import { Link } from 'react-router-dom';
import { Outlet } from "react-router-dom";

export default function Root() {
  return (
    <div>
      <header>
        <h1><Link to="/">Brewbot</Link></h1>
      </header>
        <Outlet />
      <footer>
        <p>|-|</p>
      </footer>
    </div>
  );
}
